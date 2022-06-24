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
    "version": (0, 2, 0),
    "location": "View3D > Sidebar > View > ReView",
    "category": "3D View",
}

import bpy
import mathutils


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
    quat_string = view_data[0].split(" ")
    quat_string = [float(num) for num in quat_string]
    view_data[0] = mathutils.Quaternion(quat_string)
    view_data[1] = mathutils.Vector(view_data[1])
    return view_data


def store_view():
    context = bpy.context
    props = context.scene.review_props

    view = [area for area in context.screen.areas if area.type == "VIEW_3D"][0]
    region3d = view.spaces[0].region_3d

    current_view = get_data(region3d)
    views = context.scene.review_views
    last_view = context.scene.review_last
    last_view_data = None
    last_view_data_copy = None

    if not last_view:
        # save last view if it's the first iteration
        new_view = last_view.add()
        set_data(new_view, current_view)
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
            new_view = views.add()
            set_data(new_view, current_view)

            if len(views) > get_preferences().save_count:
                views.remove(0)

    # update last view
    set_data(last_view[0], current_view)

    if not props.is_active:
        return None
    return get_preferences().update_delay


def draw_idx(layout):
    context = bpy.context
    props = context.scene.review_props
    row = layout.row()
    row.alignment = "CENTER"
    view_idx = props.view_idx
    view_count = len(context.scene.review_views)
    if view_count > 0:
        row.label(text=f"{view_idx + 1}/{view_count}")
    else:
        row.label(text="0/0")


def draw_toggle(layout):
    row = layout.row()
    row.scale_y = 2
    is_active = bpy.context.scene.review_props.is_active
    if is_active:
        row.operator("review.toggle", text="Active", icon="VIEW_CAMERA")
    else:
        row.operator("review.toggle", text="Inactive", icon="CAMERA_DATA")


def draw_ops(layout):
    layout.operator("review.switch", text="", icon="TRIA_LEFT").mode = "PREVIOUS"
    layout.operator("review.switch", text="", icon="TRIA_RIGHT").mode = "NEXT"
    layout.operator("review.switch", text="", icon="TIME").mode = "RECENT"


def get_preferences():
    return bpy.context.preferences.addons[__name__].preferences


class REVIEW_OT_toggle(bpy.types.Operator):
    bl_idname = "review.toggle"
    bl_label = "Toggle"
    bl_description = "Toggle ReView"

    def execute(self, context):
        props = context.scene.review_props
        props.is_active = not props.is_active
        if props.is_active:
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
        name="",
        description="",
        items=[
            ("NEXT", "0", ""),
            ("PREVIOUS", "1", ""),
            ("RECENT", "2", ""),
        ],
    )

    def execute(self, context):
        props = context.scene.review_props
        view_idx = props.view_idx

        view_count = len(context.scene.review_views)
        if view_count > 0:
            if self.mode == "PREVIOUS":
                if view_idx < view_count - 1:
                    props.view_idx = view_idx + 1
            elif self.mode == "NEXT":
                if view_idx > 0:
                    props.view_idx = view_idx - 1
            else:
                props.view_idx = 0

            context = bpy.context
            props = context.scene.review_props
            region_3d = context.space_data.region_3d
            views = context.scene.review_views
            # show most recent first
            recent_views = []
            for view in reversed(views):
                recent_views.append(view)
            view = get_data(recent_views[props.view_idx])
            view = convert_data(view)
            # restore saved view
            region_3d.view_rotation = view[0]
            region_3d.view_location = view[1]
            region_3d.view_distance = view[2]
            self.report({"INFO"}, f"View {props.view_idx + 1} restored")
        else:
            self.report({"ERROR"}, "No saved views")

        return {"FINISHED"}


class REVIEW_OT_clear(bpy.types.Operator):
    bl_idname = "review.clear"
    bl_label = "Clear Views"
    bl_description = "Clear all saved views"

    def execute(self, context):
        context.scene.review_views.clear()
        context.scene.review_props.view_idx = 0
        self.report({"INFO"}, "Views cleared")
        return {"FINISHED"}


class REVIEW_PT_main(bpy.types.Panel):
    bl_label = "ReView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "View"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        draw_toggle(box)
        row = box.row()
        row.alignment = "CENTER"
        draw_ops(row)
        draw_idx(box)


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
        row.label(text="Saved Views")
        row.prop(prefs, "save_count", slider=True)
        box.operator("review.clear", icon="FILE_REFRESH")


class REVIEW_MT_review_pie(bpy.types.Menu):
    bl_label = "ReView"

    def draw(self, context):
        pie = self.layout.menu_pie()
        draw_ops(pie)
        box = pie.box()
        draw_toggle(box)
        draw_idx(box)


class REVIEW_PG_properties(bpy.types.PropertyGroup):
    is_active: bpy.props.BoolProperty()
    view_idx: bpy.props.IntProperty()


class REVIEW_PG_view(bpy.types.PropertyGroup):
    view_rotation: bpy.props.StringProperty()
    view_location: bpy.props.FloatVectorProperty(subtype="XYZ")
    view_distance: bpy.props.FloatProperty()
    count: bpy.props.IntProperty()


class REVIEW_AP_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    update_delay: bpy.props.IntProperty(
        name="",
        description="The delay time in seconds between view checks",
        default=2,
        min=1,
        max=30,
    )
    save_count: bpy.props.IntProperty(
        name="",
        description="The maximum amount of saved views",
        default=10,
        min=1,
        max=20,
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.alignment = "CENTER"
        row.label(text="Keymap", icon="EVENT_OS")
        user_keymaps = context.window_manager.keyconfigs.user.keymaps["3D View"]
        keymap_items = user_keymaps.keymap_items
        layout.context_pointer_set("keymap", user_keymaps)
        row = box.row()
        keymap_item = keymap_items["wm.call_menu_pie"]
        row.prop(keymap_item, "active", text="", full_event=True)
        row.prop(keymap_item, "type", text=keymap_item.name, full_event=True)


keymaps = []
classes = (
    REVIEW_OT_toggle,
    REVIEW_OT_switch,
    REVIEW_OT_clear,
    REVIEW_PT_main,
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
    bpy.types.Scene.review_views = bpy.props.CollectionProperty(type=REVIEW_PG_view)
    bpy.types.Scene.review_last = bpy.props.CollectionProperty(type=REVIEW_PG_view)
    key_config = bpy.context.window_manager.keyconfigs.addon
    if key_config:
        keymap = key_config.keymaps.new("3D View", space_type="VIEW_3D")
        keymap_item = keymap.keymap_items.new(
            "wm.call_menu_pie", type="V", value="PRESS", shift=True, ctrl=True
        )
        keymap_item.properties.name = "REVIEW_MT_review_pie"
        keymaps.append((keymap, keymap_item))


def unregister():
    for keymap, keymap_item in keymaps:
        keymap.keymap_items.remove(keymap_item)
    keymaps.clear()
    del bpy.types.Scene.review_last
    del bpy.types.Scene.review_views
    del bpy.types.Scene.review_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
