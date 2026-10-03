"""Guard against referencing non-public android.R.drawable constants.

A typo / hidden framework resource (e.g. android.R.drawable.ic_menu_archive)
only shows up at `gradlew assembleDebug` time as
"cannot find symbol ... location: class drawable", which is a very slow
feedback loop. This test checks every android.R.drawable reference in the
Java templates against the public android.R.drawable API.
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "pydrud" / "android"

# Public constants of android.R.drawable (API level 1..current).
# https://developer.android.com/reference/android/R.drawable
PUBLIC_DRAWABLES = set(
    """
alert_dark_frame alert_light_frame arrow_down_float arrow_up_float bottom_bar
btn_default btn_default_small btn_dialog btn_dropdown btn_minus btn_plus
btn_radio btn_star btn_star_big_off btn_star_big_on
button_onoff_indicator_off button_onoff_indicator_on
checkbox_off_background checkbox_on_background dark_header dialog_frame
dialog_holo_dark_frame dialog_holo_light_frame divider_horizontal_bright
divider_horizontal_dark divider_horizontal_dim_dark
divider_horizontal_textfield edit_text editbox_background
editbox_background_normal editbox_dropdown_dark_frame
editbox_dropdown_light_frame gallery_thumb ic_btn_speak_now ic_delete
ic_dialog_alert ic_dialog_dialer ic_dialog_email ic_dialog_info ic_dialog_map
ic_input_add ic_input_delete ic_input_get ic_lock_idle_alarm
ic_lock_idle_charging ic_lock_idle_lock ic_lock_idle_low_battery ic_lock_lock
ic_lock_power_off ic_lock_silent_mode ic_lock_silent_mode_off ic_media_ff
ic_media_next ic_media_pause ic_media_play ic_media_previous ic_media_rew
ic_menu_add ic_menu_agenda ic_menu_always_landscape_portrait ic_menu_call
ic_menu_camera ic_menu_close_clear_cancel ic_menu_compass ic_menu_crop
ic_menu_day ic_menu_delete ic_menu_directions ic_menu_edit ic_menu_gallery
ic_menu_help ic_menu_info_details ic_menu_manage ic_menu_mapmode
ic_menu_month ic_menu_more ic_menu_my_calendar ic_menu_mylocation
ic_menu_myplaces ic_menu_preferences ic_menu_recent_history
ic_menu_report_image ic_menu_revert ic_menu_rotate ic_menu_save
ic_menu_search ic_menu_send ic_menu_set_as ic_menu_share ic_menu_slideshow
ic_menu_sort_alphabetically ic_menu_sort_by_size ic_menu_today
ic_menu_upload ic_menu_upload_you_tube ic_menu_view ic_menu_week ic_menu_zoom
ic_notification_clear_all ic_notification_overlay ic_partial_secure
ic_popup_disk_full ic_popup_reminder ic_popup_sync
ic_search_category_default ic_secure list_selector_background menu_frame
menu_full_frame menuitem_background picture_frame presence_audio_away
presence_audio_busy presence_audio_online presence_away presence_busy
presence_invisible presence_offline presence_online presence_video_away
presence_video_busy presence_video_online progress_horizontal
progress_indeterminate_horizontal radiobutton_off_background
radiobutton_on_background screen_background_dark
screen_background_dark_transparent screen_background_light
screen_background_light_transparent spinner_background
spinner_dropdown_background star_big_off star_big_on star_off star_on
stat_notify_call_mute stat_notify_chat stat_notify_error
stat_notify_missed_call stat_notify_more stat_notify_sdcard
stat_notify_sdcard_prepare stat_notify_sdcard_usb stat_notify_sync
stat_notify_sync_noanim stat_notify_voicemail stat_sys_data_bluetooth
stat_sys_download stat_sys_download_done stat_sys_headset
stat_sys_phone_call stat_sys_phone_call_forward stat_sys_speakerphone
stat_sys_upload stat_sys_upload_done stat_sys_vp_phone_call
stat_sys_vp_phone_call_on_hold stat_sys_warning sym_action_call
sym_action_chat sym_action_email sym_call_incoming sym_call_missed
sym_call_outgoing sym_contact_card sym_def_app_icon title_bar title_bar_tall
toast_frame zoom_plate
""".split()
)

PATTERN = re.compile(r"android\.R\.drawable\.([A-Za-z0-9_]+)")


def _source_files():
    for path in TEMPLATES_DIR.rglob("*"):
        if path.is_file() and path.suffix in {".j2", ".java", ".xml", ".py"}:
            yield path


def test_all_android_drawable_references_are_public():
    bad = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            for name in PATTERN.findall(line):
                if name not in PUBLIC_DRAWABLES:
                    bad.append(f"{path}:{lineno}: android.R.drawable.{name}")
    assert not bad, "Non-public android.R.drawable references:\n" + "\n".join(bad)


def test_icons_are_vector_only_no_legacy_drawable_map():
    """Icons render from PydrudIcons vector paths — never from the dated
    Gingerbread-era android.R.drawable bitmaps (chevron → media rewind,
    qr_code → crop tool and friends)."""
    vf = TEMPLATES_DIR / "templates" / "android" / "ViewFactory.java.j2"
    text = vf.read_text(encoding="utf-8")
    assert "getIconRes" not in text
    assert "iconResource" not in text
    code_lines = [
        line for line in text.splitlines()
        if not line.lstrip().startswith(("*", "//"))
    ]
    assert not any("android.R.drawable" in line for line in code_lines)
    # The vector path is the one icon entry point other templates can call.
    assert "PydrudIcons.drawable" in text
