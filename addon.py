import struct
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Vector

bl_info = {
    "name": "LÖVE Mesh Binary Exporter",
    "author": "TurtleP",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Export",
    "description": "Export a mesh as a flat binary for a LÖVE Mesh",
    "category": "Import-Export",
}

VERTEX = struct.Struct("<fffffffff")  # pos.xyz, uv.xy, color.rgba

HEADER = struct.Struct("<3sIIII")
HEADER_MAGIC = b"MSH"


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


class ExportLoveMesh(bpy.types.Operator, ExportHelper):
    bl_idname = "export_mesh.love_mesh"
    bl_label = "Export MSH"
    filename_ext = ".msh"

    flip_uv_u: BoolProperty(name="Flip UV U", description="Flip UV U", default=False)
    flip_uv_v: BoolProperty(name="Flip UV V", description="Flip UV V", default=False)

    export_forward: EnumProperty(
        name="Forward",
        items=[(a, a, "") for a in ("X", "Y", "Z", "-X", "-Y", "-Z")],
        default="Y",
    )

    export_up: EnumProperty(
        name="Up",
        items=[(a, a, "") for a in ("X", "Y", "Z", "-X", "-Y", "-Z")],
        default="Z",
    )

    export_texture: EnumProperty(name="Texture", items=texture_items)

    def get_uv(self, layer, index):
        if not layer:
            return 0.0, 0.0

        u, v = layer.data[index].uv
        if self.flip_uv_u:
            u = 1.0 - u
        if self.flip_uv_v:
            v = 1.0 - v
        return u, v

    def get_color(self, layer, index):
        if not layer:
            return 1.0, 1.0, 1.0, 1.0
        return tuple(layer.data[index].color)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object")
            return {"CANCELLED"}

        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()

        axis_matrix = build_axis_matrix(self.export_forward, self.export_up)
        uv_layer = mesh.uv_layers.active
        color_layer = mesh.vertex_colors.active

        vertex_size = struct.calcsize(VERTEX.format)
        vertex_count = sum(len(tri.loops) for tri in mesh.loop_triangles)

        filepath_len = len(self.export_texture)

        out = bytearray()

        header_size = struct.calcsize(HEADER.format)
        out += HEADER.pack(
            HEADER_MAGIC, vertex_count, vertex_size, filepath_len, header_size
        )

        for tri in mesh.loop_triangles:
            for loop_index in tri.loops:
                loop = mesh.loops[loop_index]
                vert = mesh.vertices[loop.vertex_index]

                pos = axis_matrix @ vert.co
                uv = self.get_uv(uv_layer, loop_index)
                color = self.get_color(color_layer, loop_index)

                out += VERTEX.pack(*pos, *uv, *color)

        out += struct.pack(f"<{filepath_len}s", bytes(self.export_texture, "utf-8"))

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
        layout.prop(self, "export_forward")
        layout.prop(self, "export_up")
        layout.prop(self, "export_texture")


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
