bl_info = {
    "name": "Model exporter",
    "description": "Exporting objects into various formats",
    "author": "Filip Ruta",
    "version": (1, 0, 0),
    "blender": (3, 0, 1),
    "category": "Import-Export"
}

import bpy
import os

from bpy.types import Operator
from bpy.props import *

# native Blender export functions
EXPORT_FUNCS = {
    "obj": bpy.ops.export_scene.obj,
    "fbx": bpy.ops.export_scene.fbx,
    "gltf": bpy.ops.export_scene.gltf,
    "glb": bpy.ops.export_scene.gltf,
    "stl": bpy.ops.export_mesh.stl,
    "usd": bpy.ops.wm.usd_export
    # add new record in format
    # "format_extension": export_function
}


def expand_options(basename, argname, values, additional_args=None):
    """Expand export options
    @:param basename - name of exported model with appended `argname`
    @:param argname - name of blender's export argument in export function
    @:param values - values of given argument
    @:param additional_args - dict of additional arguments for export function
    """
    d = {basename + "_" + value.lower(): {argname: value} for value in values}

    if additional_args:
        for args_dict in d.values():
            args_dict.update(additional_args)
    return d


EXPORT_OPTIONS_MODELS = {
    "obj": {
        "default": {},
        "obj_groups": {"group_by_object": True},
        "scale": {"global_scale": 2.0},
        "triangulate_faces": {"use_triangles": True},
        "smooth_groups": {"use_smooth_groups": True},
        "smooth_groups_bitflags": {"use_smooth_groups_bitflags": True},
        "orientation": {"axis_forward": "Z", "axis_up": "X"},
        # "correct_orientation": {"axis_forward": "Y", "axis_up": "Z"},
    },
    "fbx": {
        "default": {},
        "use_custom_props": {"use_custom_props": True},
        "use_subsurf": {"use_subsurf": True},
        "use_space_transform": {"use_space_transform": True},
        "use_tangent_space": {"use_tspace": True},
        "scale": {"global_scale": 2.0},
        "apply_unit_scale": {"apply_unit_scale": True},
        "apply_unit_scale_x2": {"global_scale": 2.0, "apply_unit_scale": True},
        "apply_unit_scale_apply_transform": {
            "global_scale": 2.0, "apply_unit_scale": True, "bake_space_transform": True
        },
        # apply scale options at the end of dict
        "orientation": {"axis_forward": "Z", "axis_up": "X"},
        **expand_options(
            "apply_scale_options", "apply_scale_options",
            ["FBX_SCALE_NONE", "FBX_SCALE_UNITS", "FBX_SCALE_CUSTOM", "FBX_SCALE_ALL"],
            {"global_scale": 2.0, "apply_unit_scale": True, "bake_space_transform": True}
        ),
        **expand_options("mesh_smooth_type", "mesh_smooth_type", ["OFF", "FACE", "EDGE"])
    },
    "stl": {
        "default": {},
        "scale": {"global_scale": 2.0},
        "use_scene_unit": {"use_scene_unit": True},
        "scale_and_scene_unit": {"global_scale": 2.0, "use_scene_unit": True},
        "scale_and_scene_unit_per_object": {
            "global_scale": 2.0, "use_scene_unit": True, "ascii": True, "batch_mode": "OBJECT"
        },
        "scale_and_scene_unit_per_object_in_ascii": {
            "global_scale": 2.0, "use_scene_unit": True, "ascii": True, "batch_mode": "OBJECT"
        },
        "ascii": {"ascii": True},
        "batch_mode": {"batch_mode": "OBJECT"},
        "orientation": {"axis_forward": "Z", "axis_up": "X"},
        "orientation_in_ascii": {"axis_forward": "Z", "axis_up": "X", "ascii": True},
        "orientation_each_object": {"batch_mode": "OBJECT", "axis_forward": "Z", "axis_up": "X"},
    },
    "glb": {
        "default": {},
        "custom_properties": {"export_extras": True},
        "export_not_y_up": {"export_yup": False},
        "apply_modifiers": {"export_apply": True},
    },
    "gltf": {
        "default": {},
        "custom_properties": {"export_format": "GLTF_EMBEDDED", "export_extras": True},
        "export_not_y_up": {"export_format": "GLTF_EMBEDDED", "export_yup": False},
        "apply_modifiers": {"export_format": "GLTF_EMBEDDED", "export_apply": True},

        "separate_default": {"export_format": "GLTF_SEPARATE"},
        "separate_custom_properties": {"export_format": "GLTF_SEPARATE", "export_extras": True},
        "separate_export_not_y_up": {"export_format": "GLTF_SEPARATE", "export_yup": False},
        "separate_apply_modifiers": {"export_format": "GLTF_SEPARATE", "export_apply": True},
        # add new export settings
        # name_of_export_settings: {"export_name": "export_value", ...}
    },
    # add new export settings
    # format: {
    #     name_of_export_settings: {"export_name": "export_value", ...}
    #     or
    #     **expand_options(object_name, export_name, ["export", "values", ...], {"export_name": "export_value", ...}
    #    )
    # }
    
}

EXPORT_OPTIONS_MATERIALS = {
    "obj": {
        "default": {},
        "write_materials": {"use_materials": False},
        "material_groups": {"group_by_material": True},
        **expand_options("path_mode", "path_mode", ["AUTO", "ABSOLUTE", "RELATIVE", "COPY"])
    },
    "fbx": {
        "default": {},
        "path_mode_copy_embed": {"path_mode": "COPY", "embed_textures": True},
        **expand_options("path_mode", "path_mode", ["AUTO", "ABSOLUTE", "RELATIVE", "COPY"]),
        **expand_options(
            "apply_scale_options", "apply_scale_options",
            ["FBX_SCALE_NONE", "FBX_SCALE_UNITS", "FBX_SCALE_CUSTOM", "FBX_SCALE_ALL"],
            {"global_scale": 2.0, "apply_unit_scale": True}
        ),
        **expand_options("mesh_smooth_type", "mesh_smooth_type", ["OFF", "FACE", "EDGE"])
    },
    "glb": {
        "default": {},
        **expand_options("export_image_format", "export_image_format", ["AUTO", "JPEG"]),
        **expand_options("export_materials", "export_materials", ["EXPORT", "PLACEHOLDER", "NONE"])
    },
    "gltf": {
        "default_embedded": {"export_format": "GLTF_EMBEDDED"},
        **expand_options(
            "export_image_format", "export_image_format", ["AUTO", "JPEG"], {"export_format": "GLTF_EMBEDDED"}
        ),
        **expand_options(
            "export_materials", "export_materials", ["EXPORT", "PLACEHOLDER", "NONE"],
            {"export_format": "GLTF_EMBEDDED"}
        ),

        "separate_default": {"export_format": "GLTF_SEPARATE"},
        "separate_textures_folder": {"export_texture_dir": "textures"},
        **expand_options(
            "separate_export_image_format", "export_image_format", ["AUTO", "JPEG"], {"export_format": "GLTF_SEPARATE"}
        ),
        **expand_options(
            "separate_export_image_format_original",
            "export_image_format", ["AUTO", "JPEG"],
            {"export_format": "GLTF_SEPARATE", "export_keep_originals": True}
        ),
        **expand_options(
            "separate_export_materials",
            "export_materials",
            ["EXPORT", "PLACEHOLDER", "NONE"],
            {"export_format": "GLTF_SEPARATE"}
        )
        # add new export settings
        # name_of_export_settings: {"export_name": "export_value", ...}
    },
    # add new export settings
    # format: {
    #     name_of_export_settings: {"export_name": "export_value", ...}
    #     or
    #     **expand_options(object_name, export_name, ["export", "values", ...], {"export_name": "export_value", ...}
    #    )
    # }
}


class EXPORT_TESTER_OT_export_tester(Operator):
    """Operator for exporting models with given export settings into selected format"""
    bl_idname = "export_tester.export"
    bl_label = "Export objects"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Exporting objects into various formats"

    export_dir_name = "exports"
    separate_collection = None
    export_dir = None

    export_enum: bpy.props.EnumProperty(
        name="Export Settings",
        description="",
        items=[
            ("ALL", "All", ""),
            ("MATERIALS", "Materials", ""),
            ("MODELS", "Models", "")
        ]
    )
    export_options = {}

    def invoke(self, content, event):
        """GUI"""
        wm = content.window_manager
        return wm.invoke_props_dialog(self)

    def create_subdir(self, name, path=None):
        if not path:
            path = self.export_dir
        sub_dir = os.path.join(path, name)
        if not os.path.exists(sub_dir):
            os.makedirs(sub_dir)
        return sub_dir

    def export_location(self, context):
        """Export location for models, blend file must be saved"""
        blend_file_path = bpy.data.filepath
        if blend_file_path == "":
            self.report({'ERROR'}, "Blend file not saved!!!")
            return None

        export_dir = os.path.join(os.path.dirname(blend_file_path), self.export_dir_name)
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
        return export_dir

    def select_object(self, name):
        """Select object of given name"""
        # proper deselect, necessary for invisible objects
        for obj in bpy.context.scene.objects:
            obj.select_set(False)
        # bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects[name].select_set(True)

    def select_objects_in_collection(self):
        """Select multiple objects in `Separate_objects` collection"""
        # proper deselect, necessary for invisible objects
        for obj in bpy.context.scene.objects:
            obj.select_set(False)
        # bpy.ops.object.select_all(action='DESELECT')
        for obj in self.separate_collection.all_objects:
            obj.select_set(True)

    def perform_export(self, context, format):
        """Export models"""
        # create subdir for given format
        sub_dir = self.create_subdir(format)

        collection_exported = False  # variable to avoid exporting models in `Separate_objects` collection twice
        for obj in context.scene.objects:
            obj_collection = obj.users_collection[0]
            if obj.type == 'MESH' and obj.visible_get():  # exports only visible objects
                if obj_collection == self.separate_collection:
                    # avoid exporting models in `Separate_objects` collection twice
                    if collection_exported:
                        continue
                    self.select_objects_in_collection()
                    collection_exported = True
                else:
                    self.select_object(obj.name)

                # Create subdir for each object
                obj_dir = self.create_subdir(obj.name, sub_dir)

                # export object into selected format with each export option
                for arg_name, kwargs in self.export_options[format].items():
                    target_file = os.path.join(obj_dir, obj.name + "_" + arg_name + "." + format)
                    EXPORT_FUNCS[format](filepath=target_file, use_selection=True, **kwargs)

        return True

    def execute(self, context):
        """Prepare for models export"""
        self.separate_collection = bpy.data.collections.get('Separate_objects', None)
        self.export_dir = self.export_location(context)

        # Which formats to export based on settings
        # If you want to limit export to fewer formats, comments this and set your own formats
        # Notice that stl has no material export options
        formats = ["obj", "fbx", "glb", "gltf", "stl"]
        # formats = ["your", "formats"]

        # set selected export options
        if self.export_enum == "ALL":
            for format in formats:
                if format == "stl":
                    self.export_options[format] = EXPORT_OPTIONS_MODELS[format]
                else:
                    self.export_options[format] = {**EXPORT_OPTIONS_MODELS[format], **EXPORT_OPTIONS_MATERIALS[format]}
        elif self.export_enum == "MATERIALS":
            self.export_options = EXPORT_OPTIONS_MATERIALS
        elif self.export_enum == "MODELS":
            self.export_options = EXPORT_OPTIONS_MODELS

        if not self.export_dir:
            return {'CANCELLED'}

        # remember mode and active object
        current_mode = bpy.context.active_object.mode
        active_obj = bpy.context.view_layer.objects.active

        # change mode to object
        if current_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # perform export into all formats
        for format in formats:
            if not self.perform_export(context, format):
                bpy.context.view_layer.objects.active = active_obj
                bpy.ops.object.mode_set(mode=current_mode)
                return {'CANCELLED'}

        # set back previous settings
        bpy.context.view_layer.objects.active = active_obj
        bpy.ops.object.mode_set(mode=current_mode)

        return {'FINISHED'}


classes = [EXPORT_TESTER_OT_export_tester]


def menu_func_export_mesh(self, context):
    """Register menu option"""
    self.layout.operator(EXPORT_TESTER_OT_export_tester.bl_idname, text="Export tester")


def register():
    """Register this plugin into Blender"""
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_mesh)


def unregister():
    """Unregister this plugin from Blender"""
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    """Main directive for running plugin from Scripting panel"""
    register()
