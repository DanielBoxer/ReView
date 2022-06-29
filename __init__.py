# Copyright (C) 2022 Daniel Boxer
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


bl_info = {
    "name": "ReView",
    "author": "Daniel Boxer",
    "description": "Automatically save and restore previous views",
    "blender": (2, 80, 0),
    "version": (1, 0, 0),
    "location": "View3D > Sidebar > View > ReView",
    "category": "3D View",
    "doc_url": "https://github.com/DanielBoxer/ReView#readme",
    "tracker_url": "https://github.com/DanielBoxer/ReView/issues",
}

import bpy
import mathutils

_is_active = False


def get_data(view):
    rotation = view.view_rotation
    location = view.view_location
    distance = view.view_distance
    return [rotation, location, distance]


def set_data(view, view_data):
    q = view_data[0]
    view.view_rotation = f"{q.w} {q.x} {q.y} {q.z}"
    view.view_location = view_data[1]
    view.view_distance = view_data[2]


def convert_data(view_data):
    quat_string = view_data[0].split()
    quat_string = [float(num) for num in quat_string]
    view_data[0] = mathutils.Quaternion(quat_string)
    view_data[1] = mathutils.Vector(view_data[1])
    return view_data


def get_current_view():
    view = [area for area in bpy.context.screen.areas if area.type == "VIEW_3D"][0]
    region3d = view.spaces[0].region_3d
    return get_data(region3d)


def add_view(view, target, is_named=False):
    new_view = target.add()
    if is_named:
        # give new view a unique name for easy collection searching
        saved_views = bpy.context.scene.review_saved
        if len(saved_views) > 1:
            # skip last element because the name is currently empty
            saved_views = [int(num.name) for num in saved_views[:-1]]
            new_view.name = str(max(saved_views) + 1)
        else:
            new_view.name = "0"
    set_data(new_view, view)


def restore_view(view_data):
    region_3d = bpy.context.space_data.region_3d
    view = convert_data(view_data)
    region_3d.view_rotation = view[0]
    region_3d.view_location = view[1]
    region_3d.view_distance = view[2]


def get_selected():
    return [view for view in bpy.context.scene.review_saved if view.is_selected]


def store_view():
    current_view = get_current_view()
    views = bpy.context.scene.review_recent
    last_view = bpy.context.scene.review_last
    last_view_data = None
    last_view_data_copy = None
    if not last_view:
        # save last view if it's the first iteration
        add_view(current_view, last_view)
    else:
        # get last view
        last_view_data = get_data(last_view[0])
        last_view_data_copy = last_view_data.copy()
        last_view_data = convert_data(last_view_data)
    if current_view == last_view_data:
        match = False
        # if the view is already saved, don't save it
        for view in views:
            if get_data(view) == last_view_data_copy:
                view.count = view.count + 1
                match = True
                break
        if not match:
            # if the user has stayed on a view for two iterations, save it
            add_view(current_view, views)
            if len(views) > get_preferences().save_count:
                views.remove(0)
    # update last view
    set_data(last_view[0], current_view)
    if not _is_active:
        return None
    return get_preferences().update_delay


def get_preferences():
    return bpy.context.preferences.addons[__name__].preferences


class REVIEW_OT_toggle(bpy.types.Operator):
    bl_idname = "review.toggle"
    bl_label = "Toggle"
    bl_description = "Toggle ReView"

    def execute(self, context):
        global _is_active
        _is_active = not _is_active
        if _is_active:
            bpy.app.timers.register(store_view)
            self.report({"INFO"}, "ReView activated")
        else:
            self.report({"INFO"}, "ReView deactivated")
        return {"FINISHED"}


class REVIEW_OT_switch(bpy.types.Operator):
    bl_idname = "review.switch"
    bl_label = "Switch"
    bl_description = "Switch"

    mode: bpy.props.EnumProperty(
        items=[("NEXT", "0", ""), ("PREVIOUS", "1", ""), ("RECENT", "2", "")]
    )

    def execute(self, context):
        props = context.scene.review_props
        view_idx = props.view_idx
        view_count = len(context.scene.review_recent)
        if view_count > 0:
            if self.mode == "PREVIOUS":
                if view_idx < view_count - 1:
                    props.view_idx = view_idx + 1
            elif self.mode == "NEXT":
                if view_idx > 0:
                    props.view_idx = view_idx - 1
            else:
                props.view_idx = 0
            views = context.scene.review_recent
            # show most recent first
            recent_views = list(reversed(views))
            view = get_data(recent_views[props.view_idx])
            restore_view(view)
            self.report({"INFO"}, f"View {props.view_idx + 1} restored")
        else:
            self.report({"ERROR"}, "No saved views")
        return {"FINISHED"}


class REVIEW_OT_clear(bpy.types.Operator):
    bl_idname = "review.clear"
    bl_label = "Clear Views"
    bl_description = "Clear all views"

    mode: bpy.props.EnumProperty(items=[("RECENT", "0", ""), ("SAVED", "1", "")])

    def execute(self, context):
        if self.mode == "RECENT":
            context.scene.review_recent.clear()
            self.report({"INFO"}, "Recent views cleared")
        else:
            context.scene.review_saved.clear()
            self.report({"INFO"}, "Saved views cleared")
        context.scene.review_props.view_idx = 0
        return {"FINISHED"}


class REVIEW_OT_save(bpy.types.Operator):
    bl_idname = "review.save"
    bl_label = "Save"
    bl_description = (
        "Save current view."
        " If no view is selected, a new view will be saved."
        " If a view is selected, it will be overwritten."
    )

    def execute(self, context):
        current_view = get_current_view()
        selected = get_selected()
        if len(selected) > 0:
            for view in selected:
                set_data(view, current_view)
                self.report({"INFO"}, f"View '{view.view_name}' saved")
        else:
            add_view(current_view, context.scene.review_saved, is_named=True)
            self.report({"INFO"}, "New view saved")
        return {"FINISHED"}


class REVIEW_OT_restore(bpy.types.Operator):
    bl_idname = "review.restore"
    bl_label = "Restore"
    bl_description = "Restore saved view"

    view_idx: bpy.props.IntProperty()

    def execute(self, context):
        view = context.scene.review_saved[self.view_idx]
        restore_view(get_data(view))
        self.report({"INFO"}, f"Restored '{view.view_name}' view")
        return {"FINISHED"}


class REVIEW_OT_delete(bpy.types.Operator):
    bl_idname = "review.delete"
    bl_label = "Delete"
    bl_description = (
        "Delete saved view. If multiple views are selected, they will also be deleted"
    )

    def execute(self, context):
        saved_views = context.scene.review_saved
        selected = get_selected()
        length = len(selected)
        if length > 0:
            # some names have an empty value if view.name is in the second for loop
            # so the names are set right before
            names = [view.name for view in selected]
            for view_idx in range(length):
                saved_views.remove(saved_views.find(names[view_idx]))
            s = "s" if length > 1 else ""
            self.report({"INFO"}, f"View{s} deleted")
        else:
            self.report({"ERROR"}, f"No view selected")
        return {"FINISHED"}


class REVIEW_PT_main(bpy.types.Panel):
    bl_label = "ReView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "View"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.alignment = "CENTER"
        row.label(text="Keymap", icon="EVENT_OS")
        row = box.row()
        maps = context.window_manager.keyconfigs.user.keymaps["3D View"].keymap_items
        row.prop(maps["wm.call_menu_pie"], "active", text="")
        row.prop(maps["wm.call_menu_pie"], "type", text="", full_event=True)


class REVIEW_PT_saved_views(bpy.types.Panel):
    bl_label = "Saved Views"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "REVIEW_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        saved_views = bpy.context.scene.review_saved
        for view_idx, view in enumerate(saved_views):
            row = box.row()
            row.prop(view, "is_selected", text="")
            split = row.split(factor=0.6)
            split.prop(view, "view_name", text="")
            split.operator(
                "review.restore", icon="RECOVER_LAST", text=""
            ).view_idx = view_idx
        row = box.row()
        row.operator("review.save", icon="FILE_TICK")
        if saved_views:
            row.operator("review.delete", icon="TRASH")


class REVIEW_PT_settings(bpy.types.Panel):
    bl_label = "Settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_parent_id = "REVIEW_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        prefs = get_preferences()
        box = layout.box()
        row = box.row()
        row.label(text="Update Delay")
        row.prop(prefs, "update_delay", slider=True)
        row = box.row()
        row.label(text="Max Views")
        row.prop(prefs, "save_count", slider=True)
        box.separator(factor=0)
        row = box.row()
        row.alignment = "CENTER"
        row.label(text="Clear Views", icon="FILE_REFRESH")
        row = box.row()
        row.operator("review.clear", text="Recent").mode = "RECENT"
        row.operator("review.clear", text="Saved").mode = "SAVED"


class REVIEW_MT_review_pie(bpy.types.Menu):
    bl_label = "ReView"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator(
            "review.switch", text="Previous", icon="TRIA_LEFT"
        ).mode = "PREVIOUS"
        pie.operator("review.switch", text="Next", icon="TRIA_RIGHT").mode = "NEXT"
        pie.operator("review.switch", text="Recent", icon="TIME").mode = "RECENT"
        box = pie.box()
        row = box.row()
        row.scale_y = 2
        if _is_active:
            row.operator("review.toggle", text="Active", icon="OUTLINER_OB_CAMERA")
        else:
            row.operator("review.toggle", text="Inactive", icon="CAMERA_DATA")
        row = box.row()
        row.alignment = "CENTER"
        view_idx = context.scene.review_props.view_idx
        view_count = len(context.scene.review_recent)
        if view_count > 0:
            row.label(text=f"{view_idx + 1}/{view_count}")
        else:
            row.label(text="0/0")


class REVIEW_PG_properties(bpy.types.PropertyGroup):
    view_idx: bpy.props.IntProperty()


class REVIEW_PG_view(bpy.types.PropertyGroup):
    view_rotation: bpy.props.StringProperty()
    view_location: bpy.props.FloatVectorProperty(subtype="XYZ")
    view_distance: bpy.props.FloatProperty()
    count: bpy.props.IntProperty()
    view_name: bpy.props.StringProperty(
        name="Name",
        description="View name. Used for organizational purposes only",
        default="Untitled",
    )
    is_selected: bpy.props.BoolProperty(
        name="Select",
        description=(
            "Select this view. Once selected, this view can be resaved or deleted"
        ),
    )


class REVIEW_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    update_delay: bpy.props.IntProperty(
        name="",
        description="The delay time in seconds between view checks",
        default=1,
        min=1,
        max=30,
    )
    save_count: bpy.props.IntProperty(
        name="",
        description="The maximum amount of recent views",
        default=10,
        min=1,
        max=50,
    )


keymaps = []
classes = (
    REVIEW_OT_toggle,
    REVIEW_OT_switch,
    REVIEW_OT_clear,
    REVIEW_OT_save,
    REVIEW_OT_restore,
    REVIEW_OT_delete,
    REVIEW_PT_main,
    REVIEW_PT_saved_views,
    REVIEW_PT_settings,
    REVIEW_MT_review_pie,
    REVIEW_PG_properties,
    REVIEW_PG_view,
    REVIEW_AP_preferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.review_props = bpy.props.PointerProperty(type=REVIEW_PG_properties)
    bpy.types.Scene.review_recent = bpy.props.CollectionProperty(type=REVIEW_PG_view)
    bpy.types.Scene.review_last = bpy.props.CollectionProperty(type=REVIEW_PG_view)
    bpy.types.Scene.review_saved = bpy.props.CollectionProperty(type=REVIEW_PG_view)
    key_config = bpy.context.window_manager.keyconfigs.addon
    if key_config:
        keymap = key_config.keymaps.new("3D View", space_type="VIEW_3D")
        keymap_item = keymap.keymap_items.new(
            "wm.call_menu_pie", type="V", value="PRESS", shift=True, ctrl=True
        )
        keymap_item.properties.name = "REVIEW_MT_review_pie"
        keymaps.append((keymap, keymap_item))


def unregister():
    if bpy.app.timers.is_registered(store_view):
        bpy.app.timers.unregister(store_view)
    for keymap, keymap_item in keymaps:
        keymap.keymap_items.remove(keymap_item)
    keymaps.clear()
    del bpy.types.Scene.review_saved
    del bpy.types.Scene.review_last
    del bpy.types.Scene.review_recent
    del bpy.types.Scene.review_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
