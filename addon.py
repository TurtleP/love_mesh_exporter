import struct
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Vector

bl_info = {
    "name": "LÖVE Mesh Binary Exporter",
    "author": "TurtleP",
    "version": (1, 1),
    "blender": (3, 0, 0),
    "location": "File > Export",
    "description": "Export a mesh as a flat binary for a LÖVE Mesh",
    "category": "Import-Export",
}

# ---------------------------
# GPU attribute definitions
# ---------------------------
DATAFORMAT = {
    "FLOAT_VEC2": 1,
    "FLOAT_VEC3": 2,
    "FLOAT_VEC4": 3,
}

ATTRIBUTE = {
    "VertexPosition": 0,
    "VertexTexCoord": 1,
    "VertexColor": 2,
}

# Central attribute table: name -> (semantic, DataFormat, struct format)
ATTRIBUTE_TABLE = {
    "VertexPosition": (ATTRIBUTE["VertexPosition"], DATAFORMAT["FLOAT_VEC3"], "fff", 0),
    "VertexTexCoord": (ATTRIBUTE["VertexTexCoord"], DATAFORMAT["FLOAT_VEC2"], "ff", 1),
    "VertexColor": (ATTRIBUTE["VertexColor"], DATAFORMAT["FLOAT_VEC4"], "ffff", 2),
}

# ---------------------------
# Struct definitions
# ---------------------------

HEADER_MAGIC = b"MSH0"
HEADER_STRUCT = struct.Struct("<4sIIIIII")   # magic, vertex_count, stride, attribute_count, attr_struct_size, texture_name_len, , size
ATTRIBUTE_STRUCT = struct.Struct("<BBB")   # semantic, dataformat, offset


def axis_vector(axis: str) -> Vector:
    sign = -1 if axis.startswith("-") else 1
    axis = axis[-1]
    return {
        "X": Vector((sign, 0, 0)),
        "Y": Vector((0, sign, 0)),
        "Z": Vector((0, 0, sign)),
    }[axis]


def build_axis_matrix(forward: str, up: str) -> Matrix:
    fwd = axis_vector(forward)
    upv = axis_vector(up)
    right = fwd.cross(upv)

    return Matrix((right, upv, fwd)).transposed()


def build_attribute_layout():
    """Compute offsets and total stride based on ATTRIBUTE_TABLE."""
    layout = []
    offset = 0
    for name, (semantic, dataformat, fmt, location) in ATTRIBUTE_TABLE.items():
        size = struct.calcsize("<" + fmt)
        layout.append((name, semantic, dataformat, location, fmt))
        offset += size
    return layout, offset



def get_mesh_textures(obj):
    textures = list()

    for slot in obj.material_slots:
        material = slot.material
        if not material or not material.use_nodes:
            continue

        tree_nodes = material.node_tree.nodes
        node = next((n for n in tree_nodes if n.type == "TEX_IMAGE"), None)
        filepath = Path(bpy.path.abspath(node.image.filepath)).resolve()
        display_name = bpy.path.display_name(filepath.as_posix())
        textures.append((display_name, filepath.name))

    return textures


def texture_items(self, context):
    obj = context.active_object
    if not obj or obj.type != "MESH":
        return []

    textures = get_mesh_textures(obj)
    return [(filepath, display_name, "") for (display_name, filepath) in textures]

AXIS_DATA = ("X", "Y", "Z", "-X", "-Y", "-Z")
ENDIANS = (("Little", "<"), ("Big", ">"))

class ExportLoveMesh(bpy.types.Operator, ExportHelper):
    bl_idname = "export_mesh.love_mesh"
    bl_label = "Export MSH"
    filename_ext = ".msh"

    flip_uv_u: BoolProperty(name="Flip UV U", description="Flip UV U", default=False) # type: ignore
    flip_uv_v: BoolProperty(name="Flip UV V", description="Flip UV V", default=False) # type: ignore

    forward_axis: EnumProperty(name="Forward", items=[(axis, axis, "") for axis in AXIS_DATA], default="Y") # type: ignore
    up_axis: EnumProperty(name="Up", items=[(axis, axis, "") for axis in AXIS_DATA], default="Z") # type: ignore

    texture_name: EnumProperty(name="Texture", items=texture_items) # type: ignore
    endian: EnumProperty(name="Vertex Endian", items=[(format, endian_type, "") for (endian_type, format) in ENDIANS], default="<") # type: ignore

    def get_uv(self, layer, index) -> tuple[float, float]:
        if not layer:
            return (0.0, 0.0)

        u, v = layer.data[index].uv
        if self.flip_uv_u:
            u = 1.0 - u

        if self.flip_uv_v:
            v = 1.0 - v

        return (u, v)

    def get_color(self, layer, index) -> tuple[float, float, float, float]:
        if not layer:
            return (1.0, 1.0, 1.0, 1.0)

        return tuple(layer.data[index].color)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object")
            return {"CANCELLED"}

        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()

        axis_matrix = build_axis_matrix(self.forward_axis, self.up_axis)
        uv_layer = mesh.uv_layers.active
        color_layer = mesh.vertex_colors.active

        layout, stride = build_attribute_layout()
        vertex_count = sum(len(tri.loops) for tri in mesh.loop_triangles)

        out = bytearray()
        header_size = struct.calcsize(HEADER_STRUCT.format)

        texture_name = self.texture_name.encode("utf-8")
        attributes_size = struct.calcsize(ATTRIBUTE_STRUCT.format)
        out += HEADER_STRUCT.pack(HEADER_MAGIC, vertex_count, stride, len(layout), attributes_size, len(texture_name), header_size)

        # Attribute table
        for _, semantic, dataformat, location, _ in layout:
            out += ATTRIBUTE_STRUCT.pack(semantic, dataformat, location)

        for tri in mesh.loop_triangles:
            for loop_index in tri.loops:
                loop = mesh.loops[loop_index]
                vert = mesh.vertices[loop.vertex_index]

                pos = axis_matrix @ vert.co
                uv = self.get_uv(uv_layer, loop_index)
                color = self.get_color(color_layer, loop_index)

                for _, semantic, _, _, format in layout:
                    struct_pack_format = f"{self.endian}{format}"
                    if semantic == ATTRIBUTE["VertexPosition"]:
                        out += struct.pack(struct_pack_format, pos.x, pos.y, pos.z)
                    elif semantic == ATTRIBUTE["VertexTexCoord"]:
                        out += struct.pack(struct_pack_format, *uv)
                    elif semantic == ATTRIBUTE["VertexColor"]:
                        out += struct.pack(struct_pack_format, *color)

        if len(texture_name):
            out += struct.pack(f"<{len(texture_name)}s", texture_name)

        obj.to_mesh_clear()
        with open(self.filepath, "wb") as f:
            f.write(out)

        self.report({"INFO"}, f"Exported {len(out)} bytes")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        layout.label(text="UV Options")
        layout.prop(self, "flip_uv_u")
        layout.prop(self, "flip_uv_v")

        layout.separator()

        layout.label(text="Export Options")
        layout.prop(self, "forward_axis")
        layout.prop(self, "up_axis")
        layout.prop(self, "texture_name")
        layout.prop(self, "endian")


def menu_func_export(self, context):
    self.layout.operator(ExportLoveMesh.bl_idname, text="MSH")


def register():
    bpy.utils.register_class(ExportLoveMesh)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ExportLoveMesh)


if __name__ == "__main__":
    register()
