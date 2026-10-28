//! GTK3 Wayland cannot create the cursor shm pool with a zero size. A few
//! non-GNOME desktops export size=0/theme="" as unset values via GSettings.
//! Normalize only invalid values in this process before creating any window;
//! never write GSettings/dconf or force XWayland/disable a WebKit sandbox.

fn valid_size(value: i32) -> bool {
    (1..=1024).contains(&value)
}

pub fn fallback(
    size: i32,
    theme: Option<&str>,
    environment_size: Option<&str>,
    environment_theme: Option<&str>,
) -> Option<(i32, String)> {
    let has_theme = theme.is_some_and(|name| !name.trim().is_empty());
    if valid_size(size) && has_theme {
        return None;
    }
    let size = if valid_size(size) {
        size
    } else {
        environment_size
            .and_then(|text| text.parse::<i32>().ok())
            .filter(|value| valid_size(*value))
            .unwrap_or(24)
    };
    let theme = if has_theme {
        theme.unwrap().to_owned()
    } else {
        environment_theme
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .unwrap_or("default")
            .to_owned()
    };
    Some((size, theme))
}

#[cfg(target_os = "linux")]
pub fn configure() -> Result<(), String> {
    use gtk::prelude::*;
    gtk::init().map_err(|error| format!("Unable to initialize GTK: {error}"))?;
    let settings = gtk::Settings::default().ok_or("GTK settings unavailable")?;
    let size = settings.property::<i32>("gtk-cursor-theme-size");
    let theme = settings.property::<Option<String>>("gtk-cursor-theme-name");
    if let Some((size, theme)) = fallback(
        size,
        theme.as_deref(),
        std::env::var("XCURSOR_SIZE").ok().as_deref(),
        std::env::var("XCURSOR_THEME").ok().as_deref(),
    ) {
        // Set positive size first: a theme change at size=0 cannot mmap its shm.
        // GTK application-priority properties do not mutate desktop settings.
        settings.set_property("gtk-cursor-theme-size", size);
        settings.set_property("gtk-cursor-theme-name", theme);
        eprintln!("OrBeats: applied process-local fallback for unset GTK cursor settings");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn valid_desktop_preferences_are_never_overridden() {
        assert_eq!(
            fallback(48, Some("Breeze"), Some("24"), Some("other")),
            None
        );
        assert_eq!(fallback(512, Some("Accessible"), None, None), None);
    }
    #[test]
    fn unset_cursor_uses_environment_then_safe_defaults() {
        assert_eq!(
            fallback(0, Some(""), Some("32"), Some("Adwaita")),
            Some((32, "Adwaita".into()))
        );
        assert_eq!(
            fallback(0, Some(""), None, None),
            Some((24, "default".into()))
        );
        assert_eq!(
            fallback(0, Some("Valid"), Some("48"), Some("other")),
            Some((48, "Valid".into()))
        );
        assert_eq!(
            fallback(48, None, Some("24"), Some("other")),
            Some((48, "other".into()))
        );
    }
    #[test]
    fn invalid_and_overflowing_sizes_never_reach_shm_allocation() {
        for size in [i32::MIN, -1, 0, 1025, i32::MAX] {
            for env in [
                None,
                Some("0"),
                Some("-1"),
                Some("huge"),
                Some("9999999999999999"),
            ] {
                assert_eq!(
                    fallback(size, Some(" "), env, Some(" ")),
                    Some((24, "default".into()))
                );
            }
        }
    }
}
