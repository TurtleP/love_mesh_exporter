import struct

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


class ExportLoveMesh(bpy.types.Operator, ExportHelper):
    bl_idname = "export_mesh.love_mesh"
    bl_label = "Export MSH"
    filename_ext = ".msh"

    flip_uv_u: BoolProperty(name="Flip UV U", description="Flip UV U", default=False)
    flip_uv_v: BoolProperty(name="Flip UV V", description="Flip UV V", default=False)

    export_forward: EnumProperty(
        name="Forward",
        items=[
            ("X", "X", ""),
            ("Y", "Y", ""),
            ("Z", "Z", ""),
            ("-X", "-X", ""),
            ("-Y", "-Y", ""),
            ("-Z", "-Z", ""),
        ],
        default="Y",
    )

    export_up: EnumProperty(
        name="Up",
        items=[
            ("X", "X", ""),
            ("Y", "Y", ""),
            ("Z", "Z", ""),
            ("-X", "-X", ""),
            ("-Y", "-Y", ""),
            ("-Z", "-Z", ""),
        ],
        default="Z",
    )

    def axis_vector(self, axis) -> Vector:
        sign = -1 if axis.startswith("-") else 1
        axis = axis[-1]
        if axis == "X":
            return Vector((sign, 0, 0))
        if axis == "Y":
            return Vector((0, sign, 0))
        if axis == "Z":
            return Vector((0, 0, sign))

    def export_position(self, pos):
        fwd = self.axis_vector(self.export_forward)
        up = self.axis_vector(self.export_up)

        right = fwd.cross(up)

        mat = Matrix(
            (
                right,
                up,
                fwd,
            )
        ).transposed()

        return mat @ pos

    def get_uvs(self, layer, index) -> list[float]:
        if layer is not None:
            u, v = layer.data[index].uv
            if self.flip_uv_u:
                u = 1.0 - u
            if self.flip_uv_v:
                v = 1.0 - v
            return [u, v]
        return [0.0, 0.0]

    def get_color(self, layer, index) -> list[float]:
        if layer is not None:
            return layer.data[index].color
        return [1.0, 1.0, 1.0, 1.0]

    def execute(self, context):
        obj = bpy.context.active_object
        if not obj or obj.type != "MESH":
            raise RuntimeError("Select a mesh object")

        mesh = obj.to_mesh()
        mesh.calc_loop_triangles()

        out = bytearray()
        VERTEX_FMT = "<fffffffff"  # xyz uv rgba

        uv_layer = mesh.uv_layers.active
        color_layer = mesh.vertex_colors.active

        for tri in mesh.loop_triangles:
            for loop_index in tri.loops:
                loop = mesh.loops[loop_index]
                vert = mesh.vertices[loop.vertex_index]

                pos = self.export_position(vert.co)
                u, v = self.get_uvs(uv_layer, loop_index)
                r, g, b, a = self.get_color(color_layer, loop_index)
                out += struct.pack(VERTEX_FMT, pos.x, pos.y, pos.z, u, v, r, g, b, a)

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
