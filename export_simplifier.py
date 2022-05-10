bl_info = {
    "name": "Export Simplifier",
    "description": "Simplify exports to other 3D applications",
    "author": "Filip Ruta",
    "version": (1, 0, 0),
    "blender": (3, 0, 1),
    "category": "Import-Export"
}
import bpy
import os

from bpy.props import *
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator, Panel, Scene, PropertyGroup


def create_subdir(name, path=None):
    """Check if dir exists and is accessible, create a new one if it doesn't exist"""
    if not path:
        path = bpy.context.scene.simplifier.export_dir
    sub_dir = os.path.join(path, name)

    if not os.path.exists(sub_dir):
        try:
            os.makedirs(sub_dir)
        except PermissionError:
            return ""
    return sub_dir


def unwrap():
    """Unwrap model if wasn't already unwrapped based on `model_unwrapped` property, firstly apply scale"""
    if not bpy.context.scene.model_unwrapped:
        # Apply scale for correct unwrapping
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(island_margin=0.06)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.scene.model_unwrapped = True


def draw_split(layout, pointer_prop, label, property_name, factor=0.4):
    """Add panel entry for label and corresponding property"""
    row = layout.row(align=True)
    split = row.split(factor=factor)
    c = split.column()
    c.label(text=label)
    split = split.split()
    c = split.column()
    c.prop(pointer_prop, property_name, text="")
    return row


class SIMPLIFIER_OT_filebrowser(Operator, ExportHelper):
    """Filebrowser for selecting export dir"""

    bl_idname = "simplifier.file_browser"
    bl_label = "Select export folder"

    filepath = StringProperty(subtype='DIR_PATH')
    filename_ext = "/"
    use_filter_folder = True

    def execute(self, context):
        """Select export folder"""
        if not os.path.isdir(self.filepath):
            self.report({'ERROR'}, "Not a directory, please select a directory, not a file.")
            return {'CANCELLED'}
        context.scene.simplifier.export_dir = self.filepath
        return {'FINISHED'}


# -----------------------------------------------------------------------

class BakeDataGroup(bpy.types.PropertyGroup):
    """Data for texture baking"""
    texture_name: bpy.props.StringProperty(
        name="Texture name",
        description="""Choose a name of your texture.
        Warning: If the name already exists, the texture will be overwritten"""
    )

    width: bpy.props.IntProperty(
        name="Width",
        min=0,
        default=1024
    )

    use_texture: bpy.props.BoolProperty(
        name="Use texture in material",
        description="Add baked texture into existing material and use it",
        default=False
    )

    height: bpy.props.IntProperty(
        name="Height",
        min=0,
        default=1024
    )

    bake_types: bpy.props.EnumProperty(
        name="File format",
        default={"DIFFUSE"},
        description="Which textures to bake",
        options={"ENUM_FLAG"},
        items=[
            ("DIFFUSE", "Diffuse", "", 1),
            ("NORMAL", "Normal", "", 2),
            ("ROUGHNESS", "Roughness", "", 4),
            ("GLOSSY", "Glossy", "", 8),
            ("ALPHA", "Alpha", "Works only on principled materials properly", "INFO", 16)
            # ("TRANSMISSION", "Transmission", "")
            # ("AO", "AO", "")
        ]
    )

    device: bpy.props.EnumProperty(
        name="Device",
        description="""Device used for baking.
         You might have to enable GPU options in preferences->System->CUDA. Not available on all devices""",
        default="CPU",
        items=[("CPU", "CPU", ""), ("GPU", "GPU", "")]
    )

    export_after: bpy.props.BoolProperty(
        name="Export model after bake",
        description="Automatically export model after bake",
        default=False
    )


# -----------------------------------------------------------------------

class MaterialDataGroup(bpy.types.PropertyGroup):
    """Data for material list"""
    material: bpy.props.PointerProperty(
        name="Material",
        type=bpy.types.Material
    )

    selected: BoolProperty(
        default=False
    )


# -----------------------------------------------------------------------

class SIMPLIFIER_UL_material_list(bpy.types.UIList):
    """List for selecting materials to bake"""
    bl_idname = "SIMPLIFIER_UL_material_list"
    bl_label = "Update materials"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        mat = item.material

        # No need to redraw if object is not selected
        if mat is None:
            return

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # split line before setting properties
            split = layout.split(factor=0.1)

            split.prop(item, "selected", text="")
            split.prop(mat, "name", text="", emboss=False, icon_value=layout.icon(mat))

        elif self.layout_type in {'GRID'}:
            layout.prop(item, "selected", text="")
            layout.label(text=mat.name, icon_value=layout.icon(mat))


# -----------------------------------------------------------------------

class SIMPLIFIER_OT_update_material_list(bpy.types.Operator):
    """Operator to update materials of selected object"""
    bl_idname = "simplifier.update_material_list"
    bl_label = "Update materials"
    bl_description = "Reload materials of selected object"

    def execute(self, context):
        scene = context.scene

        # Save the previous selection
        old_selection = {}
        for mat in scene.material_group:
            old_selection[mat.material.name] = mat.selected

        # Remove materials from list
        scene.material_group.clear()
        active_obj = bpy.context.active_object
        if not active_obj:
            return {'FINISHED'}
        bpy.context.object.active_material_index = scene.custom_index

        # Add new materials to list
        for mat in active_obj.material_slots:
            item = scene.material_group.add()
            item.name = mat.name
            item.material = mat.material
            # Check if material was selected previously and if so keep it selected
            if mat.name in old_selection and old_selection[mat.name] is True:
                item.selected = True
            else:
                item.selected = False

        return {'FINISHED'}


# -----------------------------------------------------------------------

class SIMPLIFIER_PT_bake_panel(bpy.types.Panel):
    """Panel for texture baking purposes"""

    bl_label = "Bake textures"
    bl_idname = "XD12_PT_bake_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_context = "objectmode"
    bl_parent_id = "SIMPLIFIER_PT_export_panel"

    def draw_header(self, context):
        """Draws header for bake panel"""
        layout = self.layout
        scene = context.scene
        simplifier = scene.simplifier
        layout.prop(simplifier, "bake", text="")

    def draw(self, context):
        """Draws content of bake panel"""
        layout = self.layout
        scene = context.scene
        baker = scene.baker
        simplifier = scene.simplifier
        layout.active = scene.simplifier.bake

        # Create panel properties
        draw_split(layout, baker, "Texture name", "texture_name")
        row = layout.row(align=True)
        row.prop(baker, "width")
        row.prop(baker, "height")
        draw_split(layout, baker, "Connect textures", "use_texture")
        row = layout.row(align=True)
        unwrap_text = "Model will be unwrapped, old UV will be replaced" if simplifier.unwrap else "Model won't be unwrapped"
        row.label(text=unwrap_text, icon="INFO")
        row = layout.row(align=True)
        row.label(text="Bake types:", icon="QUESTION", )
        row = layout.row(align=True)
        row.prop(baker, "bake_types")

        # Create list of materials to bake
        layout.row(align=True)
        layout.label(text="Select which materials to bake")
        layout.template_list(
            "SIMPLIFIER_UL_material_list", "", scene, "material_group", scene, "custom_index",
            rows=3, maxrows=3, columns=2, type='DEFAULT'
        )

        # Add button to update materials
        row = layout.row(align=True)
        row.operator("simplifier.update_material_list", icon="LINENUMBERS_ON")

        # Add button to choose device used for baking (with check if device is available)
        row = draw_split(layout, baker, "Device", "device")
        row.enabled = bpy.context.preferences.addons["cycles"].preferences.has_active_device()

        draw_split(layout, baker, "Export after bake", "export_after")
        row = layout.row(align=True)
        # Button to start baking
        text = "Bake textures and Export models" if baker.export_after else "Bake textures"
        row.operator("simplifier.bake", text=text)


# -----------------------------------------------------------------------


class SIMPLIFIER_OT_bake(bpy.types.Operator):
    """Operator for texture baking"""
    bl_idname = "simplifier.bake"
    bl_label = "Bake textures"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Bake textures"

    texture_nodes = {}
    textures_to_create = {}
    images = []

    def texture_exists(self, texture_name, baker):
        """Checks if image with given name exists"""
        for img in bpy.data.images:
            if img.name == texture_name and img.size[0] == baker.width and img.size[1] == baker.height:
                return True
            if img.name == texture_name and (img.size[0] != baker.width or img.size[1] != baker.height):
                raise AttributeError("Cannot change textures resolution")
        return False

    def generate_texture(self, context, texture_name):
        """Generate necessary textures for baking"""
        scene = context.scene
        baker = scene.baker

        # Check if texture name was given
        if baker.texture_name.strip() == "":
            self.report({'ERROR'}, "No texture name set.")
            return False

        self.textures_to_create = {name.lower() for name in baker.bake_types}

        for map_name in self.textures_to_create:
            try:
                if not self.texture_exists(texture_name + "_" + map_name, baker):
                    bpy.data.images.new(
                        name=texture_name + "_" + map_name, width=baker.width, height=baker.height, alpha=False
                    )
            except AttributeError:
                self.report(
                    {'ERROR'},
                    "Cannot change resolution of existing texture, delete texture in Blender or use another name."
                )
                return False

        return True

    def clean_up(self, context, specific_texture=None):
        """Removes generated textures, if `specific_texture` is set, then removes only that texture"""
        for node_tree, node_dict in self.texture_nodes.items():
            if not specific_texture:
                for node in node_dict.values():
                    node_tree.nodes.remove(node)
            else:
                node_tree.nodes.remove(node_dict[specific_texture])

    def save_textures(self, context):
        """Saves baked textures to drive"""
        simplifier = context.scene.simplifier
        first = next(iter(self.texture_nodes))
        obj_name = bpy.context.selected_objects[0].name
        obj_dir = create_subdir(obj_name, simplifier.export_dir)
        if not obj_dir:
            self.report(
                {'ERROR'},
                "Cannot access chosen dir."
            )
            return False
        texture_dir = create_subdir("baked_textures", obj_dir)
        if not texture_dir:
            self.report(
                {'ERROR'},
                "Cannot access chosen dir."
            )
            return False
        for tex_node in self.texture_nodes[first].values():
            if hasattr(tex_node, "image"):
                tex_node.image.filepath_raw = os.path.join(texture_dir, tex_node.image.name + ".png")
                tex_node.image.file_format = 'PNG'
                tex_node.image.save()
        return True

    def prepare_new_nodes(self, context, node_tree, connect_to_outputs):
        """Creates new node setup for baking or eventually new texture connections to existing materials"""
        nodes = node_tree.nodes
        baker = context.scene.baker
        output_node = None
        # Find output node by type (search by name is not secure)
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
        if not output_node:
            return False

        # If connect textures option isn't set, remember previous connection to output node for reconnecting after bake
        old_node_connected_to_output = output_node.inputs["Surface"].links[0].from_node
        old_node_connected_socket = output_node.inputs["Surface"].links[0].from_socket.name

        max_y_coord: int

        self.texture_nodes[node_tree] = {}

        for map_name in self.textures_to_create:
            # Create new texture nodes for all maps
            self.texture_nodes[node_tree][map_name] = nodes.new("ShaderNodeTexImage")
            self.texture_nodes[node_tree][map_name].image = bpy.data.images[baker.texture_name + "_" + map_name]
            if map_name != "diffuse":
                # for non-diffuse textures select proper colorspace type
                self.texture_nodes[node_tree][map_name].image.colorspace_settings.name = "Non-Color"

        if (baker.use_texture or baker.export_after) and self.textures_to_create:
            # calculate position of free space in material editor
            max_y_coord = self.get_max_y_node_coordinate(output_node.location, nodes)
            # create new Principled shader and set its location
            principled_node = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            self.texture_nodes[node_tree]["principled"] = principled_node
            principled_node.location = (-100, max_y_coord + 200)

            # set textures locations and make links between nodes
            if "diffuse" in self.textures_to_create:
                self.texture_nodes[node_tree]["diffuse"].location = (-400, max_y_coord + 300)
                node_tree.links.new(self.texture_nodes[node_tree]["diffuse"].outputs[0], principled_node.inputs[0])
            if "roughness" in self.textures_to_create:
                self.texture_nodes[node_tree]["roughness"].location = (-400, max_y_coord + 20)
                node_tree.links.new(self.texture_nodes[node_tree]["roughness"].outputs[0], principled_node.inputs[9])
            if "normal" in self.textures_to_create:
                # for normal map create normal map node
                normal_map_node = nodes.new("ShaderNodeNormalMap")
                normal_map_node.location = (-300, max_y_coord - 600)
                self.texture_nodes[node_tree]["normal_map_node"] = normal_map_node
                node_tree.links.new(self.texture_nodes[node_tree]["normal"].outputs[0], normal_map_node.inputs[1])
                self.texture_nodes[node_tree]["normal"].location = (-700, max_y_coord - 600)
                node_tree.links.new(normal_map_node.outputs[0], principled_node.inputs[22])
            if "alpha" in self.textures_to_create:
                self.texture_nodes[node_tree]["alpha"].location = (-400, max_y_coord - 300)
                node_tree.links.new(self.texture_nodes[node_tree]["alpha"].outputs[0], principled_node.inputs[21])

        if baker.use_texture or baker.export_after:
            # Create lambda function for connecting shader to the output node after baking.
            # Uses lambda, so we don't have to keep reference or search for the principled shader
            connect_to_output = lambda: node_tree.links.new(principled_node.outputs[0], output_node.inputs[0])
            connect_to_outputs["new"].append(connect_to_output)
            if not baker.use_texture:
                connect_old_to_output = lambda: node_tree.links.new(
                    old_node_connected_to_output.outputs[old_node_connected_socket], output_node.inputs[0])
                connect_to_outputs["old"].append(connect_old_to_output)

        return True

    def set_nodes_as_active(self, texture_type):
        """In each material's node_tree set nodes necessary for bake as active"""
        for node_tree, tex_nodes in self.texture_nodes.items():
            nodes = node_tree.nodes
            texture_node = tex_nodes[texture_type]
            nodes.active = texture_node

    def get_max_y_node_coordinate(self, output_location, nodes):
        """calculate Y position for new nodes above the existing ones"""
        x_out = output_location[0]
        y_out = output_location[1]
        max_y_coord = 0
        for node in nodes:
            # search max Y coordinate in range (-500,0) relative to output node
            if (x_out - 500) < node.location[0] < x_out:
                if node.location[1] > max_y_coord:
                    max_y_coord = node.location[1]
        # Return increased value of max found Y coordinate
        return max_y_coord + 1000

    def bake_textures(self, context, materials):
        """Bake textures of selected type"""
        scene = context.scene
        baker = scene.baker
        connect_to_outputs = {
            "new": [],
            "old": []
        }
        self.texture_nodes = {}

        for material in materials:
            # If material didn't use nodes, use them
            material.use_nodes = True
            node_tree = material.node_tree

            if not self.prepare_new_nodes(context, node_tree, connect_to_outputs):
                self.report({'ERROR'}, "Output node is missing in %s material." % material.name)
                return False

                # Save previously used renderer
        renderer_used = bpy.context.scene.render.engine
        # Set rendering engine to Cycles (Eevee doesn't support baking)
        bpy.context.scene.render.engine = 'CYCLES'
        # Set device to our preference
        bpy.context.scene.cycles.device = baker.device

        # Bake arguments
        bake_kwargs = {
            "diffuse": {
                "type": "DIFFUSE", "pass_filter": {'COLOR'},
                "margin": 3, "width": baker.width, "height": baker.height,
                "target": "IMAGE_TEXTURES", "use_clear": True
            },
            "alpha": {
                "type": "GLOSSY", "pass_filter": {'COLOR'},
                "width": baker.width, "height": baker.height,
                "margin": 3, "target": "IMAGE_TEXTURES", "use_clear": True
            },
            "glossy": {
                "type": "GLOSSY", "pass_filter": {'COLOR'},
                "width": baker.width, "height": baker.height,
                "margin": 3, "target": "IMAGE_TEXTURES", "use_clear": True
            },
            "normal": {
                "type": "NORMAL",
                "width": baker.width, "height": baker.height,
                "margin": 3, "target": "IMAGE_TEXTURES", "use_clear": True
            },
            "roughness": {
                "type": "ROUGHNESS",
                "width": baker.width, "height": baker.height,
                "margin": 3, "target": "IMAGE_TEXTURES", "use_clear": True
            }
        }

        try:
            for map_name in self.textures_to_create:
                self.set_nodes_as_active(map_name)
                bpy.ops.object.bake(**bake_kwargs[map_name])
        except RuntimeError:
            self.report({'ERROR'}, "Texture name refers to image which was deleted on disk, please use another name.")
            self.clean_up(context)
            return False
        finally:
            # Switch back to previously used render engine
            bpy.context.scene.render.engine = renderer_used

        if not self.save_textures(context):
            self.clean_up(context)

        if baker.use_texture or baker.export_after:
            # Call previously saved lambda function to connect shader to output
            for connect in connect_to_outputs["new"]:
                connect()
            # Export call
            if baker.export_after:
                bpy.ops.simplifier.export()
            # Reconnect old connection to output node
            if not baker.use_texture:
                for connect in connect_to_outputs["old"]:
                    connect()

        if not baker.use_texture:
            # Delete all nodes created for baking purposes
            self.clean_up(context)

        if "glossy" in self.textures_to_create and baker.use_texture:
            # Delete glossy node which isn't used in material node setup
            self.clean_up(context, "glossy")

        return True

    def execute(self, context):
        """Perform bake"""
        scene = context.scene
        baker = scene.baker
        simplifier = scene.simplifier
        context.scene.model_unwrapped = False

        # Is bake allowed?
        if not scene.simplifier.bake:
            return {'CANCELLED'}

        # Only one object must be selected
        if len(context.selected_objects) != 1:
            self.report({'ERROR'}, "One object needs to be selected")
            return {'CANCELLED'}

        # Is correct destination for export selected?
        if baker.export_after and not os.path.exists(simplifier.export_dir):
            self.report({'ERROR'}, "Cannot access chosen dir.")
            return {'CANCELLED'}

        if simplifier.unwrap:
            unwrap()
        if not simplifier.unwrap and not bpy.context.object.data.uv_layers:
            self.report(
                {'ERROR'},
                """Object has no UV map and unwrap is not selected.
            Please check the unwrap option or unwrap model manually."""
            )
            self.clean_up(context)
            return {'CANCELLED'}

        # Extract only selected materials
        selected_materials = [
            mat.material for mat in scene.material_group if
            mat.selected is True and mat.material.name in context.active_object.material_slots
        ]
        # Are any materials selected?
        if selected_materials == []:
            self.report({'ERROR'}, "No materials selected")
            return {'CANCELLED'}

        if not self.generate_texture(context, baker.texture_name):
            self.clean_up(context)
            return {'CANCELLED'}

        if not self.bake_textures(context, selected_materials):
            self.clean_up(context)
            return {'CANCELLED'}

        return {'FINISHED'}

        # -----------------------------------------------------------------------


class SIMPLIFIER_PT_export_panel(Panel):
    bl_idname = 'SIMPLIFIER_PT_export_panel'
    bl_label = 'Export Simplifier Panel'
    bl_space_type = 'VIEW_3D'
    bl_category = "Tool"
    bl_region_type = 'UI'
    bl_context = "objectmode"

    def draw(self, context):
        """Draw content of export panel"""
        simplifier = context.scene.simplifier
        layout = self.layout

        draw_split(layout, simplifier, "File format", "format")
        if simplifier.format == "GLTF":
            draw_split(layout, simplifier, "glTF Variation", "gltf_format")
        draw_split(layout, simplifier, "3D software", "software")
        draw_split(layout, simplifier, "Unwrap model", "unwrap")

        row = draw_split(layout, simplifier, "Destination", "export_dir")
        row.operator("simplifier.file_browser", icon="FILE_FOLDER", text="")

        row = layout.row(align=True)
        row.operator('simplifier.export', text='Export Only')


class ExportDataGroup(PropertyGroup):
    """Data for export purposes"""
    export_dir: bpy.props.StringProperty(
        name="Destination",
        description="Destination for exported data",
        default="",
    )

    format: bpy.props.EnumProperty(
        name="File format",
        description="",
        default="FBX",
        items=[
            ("FBX", "fbx", ""),
            ("GLTF", "glTF", ""),
            ("OBJ", "obj", "")
        ]
    )
    gltf_format: bpy.props.EnumProperty(
        name="GLTF format",
        description="",
        items=[
            ("GLTF_SEPARATE", "Separate", "gltf text format"),
            ("GLTF_EMBEDDED", "Embedded", "gltf text format"),
            ("GLB", "Binary", "glb binary format")
        ]
    )
    software: bpy.props.EnumProperty(
        name="3D Software",
        description="Which software will the model be used in",
        items=[
            ("UNREAL", "Unreal Engine", ""),
            # ("UNITY", "Unity", "")
        ]
    )
    unwrap: bpy.props.BoolProperty(
        name="Unwrap",
        description="Use smart UV project to unwrap your model",
        default=False
    )

    bake: bpy.props.BoolProperty(
        name="Bake",
        description="Bake textures",
        default=False
    )


############################################################

class SIMPLIFIER_OT_export(Operator):
    """Operator for exporting and repairing models"""
    bl_idname = "simplifier.export"
    bl_label = "Simplify object export"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Simplify exports to other 3D applications"

    def deselect_all_objects(self):
        """Deselect all objects (including invisible)"""
        # proper deselect, necessary for invisible objects
        for obj in bpy.context.scene.objects:
            obj.select_set(False)

    def select_object(self, name):
        """select object with given name"""
        self.deselect_all_objects()
        bpy.data.objects[name].select_set(True)

    def correct_origin(self, obj):
        """Set correct origin"""
        obj.location = (0.0, 0.0, 0.0)

    def apply_transform(self):
        """Apply all object transforms"""
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    #####################################################

    def export_unreal(self, context, obj_dir, obj_name):
        """Repair and export models for Unreal Engine"""
        objects = bpy.context.selected_objects
        extension: str
        if self.data.format == "GLTF" and self.data.gltf_format == "GLB":
            extension = "glb"
        else:
            extension = self.data.format.lower()
        target_file = os.path.join(obj_dir, obj_name + "." + extension)

        if self.data.format == "FBX":
            if len(objects) == 1:
                self.correct_origin(objects[0])
            if self.data.unwrap:
                unwrap()
            bpy.ops.export_scene.fbx(
                filepath=target_file, use_selection=True, mesh_smooth_type="FACE", bake_space_transform=True
            )
        elif self.data.format == "OBJ":
            if len(objects) == 1:
                self.correct_origin(objects[0])
            if self.data.unwrap:
                unwrap()
            bpy.ops.export_scene.obj(
                filepath=target_file, use_selection=True, axis_forward="Y", axis_up="Z", global_scale=100.0
            )
        elif self.data.format == "GLTF":
            if len(objects) == 1:
                self.correct_origin(objects[0])
            self.apply_transform()
            if self.data.unwrap:
                unwrap()
            bpy.ops.export_scene.gltf(
                filepath=target_file, use_selection=True, export_apply=True, export_format=self.data.gltf_format
            )

    def export_unity(self, context, obj_dir, obj_name):
        """NOT IMPLEMETED -- Repair and export models for Unreal Engine"""
        pass

    ######################################################

    def clean_up(self, context):
        """delete duplicated objects"""
        bpy.ops.object.delete()

    def perform_export(self, context):
        """Export objects into selected software"""
        obj_name = bpy.context.selected_objects[0].name
        bpy.ops.object.duplicate(linked=False)

        obj_dir = create_subdir(obj_name, self.data.export_dir)
        if not obj_dir:
            self.report(
                {'ERROR'},
                "Cannot access chosen dir."
            )
            self.clean_up(context)
            return False

        if self.data.software == "UNREAL":
            self.export_unreal(context, obj_dir, obj_name)
        elif self.data.software == "UNITY":
            self.export_unity(context, obj_dir, obj_name)
        else:
            self.clean_up(context)
            raise NotImplementedError("This software is not supported")

        self.clean_up(context)
        return True

    def set_original_configuration(self, mode, selected, active):
        """Set previously selected mode and active and selected objects"""
        for obj in selected:
            self.select_object(obj.name)
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.mode_set(mode=mode)

    def execute(self, context):
        """Perform export"""
        self.data = context.scene.simplifier
        # set that model hasn't been unwrapped yet
        context.scene.model_unwrapped = False

        if len(bpy.context.selected_objects) == 0:
            self.report({'ERROR'}, "No models selected, please select models you want to export")
            return {'CANCELLED'}

        # remember selection
        current_mode = bpy.context.active_object.mode
        active_obj = bpy.context.view_layer.objects.active
        selected_objects = bpy.context.selected_objects

        if current_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        if not self.perform_export(context):
            self.set_original_configuration(current_mode, selected_objects, active_obj)
            return {'CANCELLED'}

        self.set_original_configuration(current_mode, selected_objects, active_obj)
        self.report({'INFO'}, "Model successfully exported")
        return {'FINISHED'}


classes = [
    SIMPLIFIER_OT_export, ExportDataGroup, SIMPLIFIER_PT_export_panel, BakeDataGroup, SIMPLIFIER_PT_bake_panel,
    SIMPLIFIER_OT_bake, MaterialDataGroup, SIMPLIFIER_UL_material_list, SIMPLIFIER_OT_update_material_list,
    SIMPLIFIER_OT_filebrowser
]


def register():
    """Register this plugin into Blender and set helper properties"""
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    Scene.simplifier = PointerProperty(type=ExportDataGroup)

    bpy.types.Scene.baker = PointerProperty(type=BakeDataGroup)
    bpy.types.Scene.material_group = CollectionProperty(type=MaterialDataGroup)
    bpy.types.Scene.custom_index = bpy.props.IntProperty()
    bpy.types.Scene.model_unwrapped = bpy.props.BoolProperty()


def unregister():
    """Unregister this plugin from Blender and delete helper properties"""
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.model_unwrapped
    del bpy.types.Scene.custom_index
    del bpy.types.Scene.material_group
    del bpy.types.Scene.baker

    del bpy.types.Scene.simplifier


if __name__ == "__main__":
    """Main directive for running plugin from Scripting panel"""
    register()
