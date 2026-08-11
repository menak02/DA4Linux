use std::process::Command;
use crate::dsp::DAX3Profile;
use crate::generator;

pub fn apply_dsp_profile(profile: &DAX3Profile) -> Result<(), String> {
    // 1. Unload existing filter chain if any
    let _ = Command::new("pw-cli")
        .arg("unload-module")
        .arg("libpipewire-module-filter-chain")
        .output();

    // 2. Generate SPA-JSON string
    let nodes_str = generator::generate_filter_graph(profile, "lv2");
    
    // We construct the full args string
    let args = format!(
        r#"{{
            "node.description": "DA4Linux DSP",
            "media.name": "DA4Linux DSP",
            "filter.graph": {{
                "nodes": [
{nodes_str}
                ]
            }},
            "capture.props": {{
                "node.name": "da4linux_input",
                "media.class": "Audio/Sink"
            }},
            "playback.props": {{
                "node.name": "da4linux_output",
                "node.passive": true
            }}
        }}"#
    );

    let output = Command::new("pw-cli")
        .arg("load-module")
        .arg("libpipewire-module-filter-chain")
        .arg(args)
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let err = String::from_utf8_lossy(&output.stderr);
        return Err(format!("pw-cli failed: {}", err));
    }

    Ok(())
}

pub fn detect_plugins() -> Vec<String> {
    let mut plugins = Vec::new();
    let lv2_paths = vec![
        "/usr/lib/lv2",
        "/usr/lib64/lv2",
        "/usr/lib/x86_64-linux-gnu/lv2",
    ];

    for path in lv2_paths {
        let p = std::path::Path::new(path);
        if p.join("lsp-plugins.lv2").exists() {
            if !plugins.contains(&"lsp-plugins-lv2".to_string()) {
                plugins.push("lsp-plugins-lv2".to_string());
            }
        }
        if p.join("calf.lv2").exists() {
            if !plugins.contains(&"calf-plugins".to_string()) {
                plugins.push("calf-plugins".to_string());
            }
        }
    }

    plugins
}

pub fn bypass_dsp_profile() -> Result<(), String> {
    let output = Command::new("pw-cli")
        .arg("unload-module")
        .arg("libpipewire-module-filter-chain")
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let err = String::from_utf8_lossy(&output.stderr);
        if !err.contains("No such file or directory") && !err.contains("not found") {
            return Err(format!("pw-cli unload failed: {}", err));
        }
    }

    Ok(())
}

pub fn restart_pipewire() -> Result<(), String> {
    // 1. Detect and restart via systemd if active
    let is_systemd = Command::new("systemctl")
        .args(&["--user", "is-active", "pipewire"])
        .output()
        .map(|o| o.status.success() || String::from_utf8_lossy(&o.stdout).trim() == "active")
        .unwrap_or(false);

    if is_systemd {
        let output = Command::new("systemctl")
            .args(&["--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"])
            .output()
            .map_err(|e| format!("Failed to run systemctl: {}", e))?;
        if !output.status.success() {
            return Err(format!(
                "systemctl failed: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
        return Ok(());
    }

    // 2. Detect and restart via runit's sv
    let has_sv = Command::new("which")
        .arg("sv")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    if has_sv {
        let output = Command::new("sv")
            .args(&["restart", "pipewire", "pipewire-pulse", "wireplumber"])
            .output()
            .map_err(|e| format!("Failed to run sv: {}", e))?;
        if output.status.success() {
            return Ok(());
        }
    }

    // 3. Detect and restart via OpenRC
    let has_rc = Command::new("which")
        .arg("rc-service")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    if has_rc {
        let output = Command::new("rc-service")
            .args(&["pipewire", "restart"])
            .output()
            .map_err(|e| format!("Failed to run rc-service: {}", e))?;
        if output.status.success() {
            return Ok(());
        }
    }

    // 4. Fallback: manual process restart
    let _ = Command::new("pkill").arg("pipewire-pulse").output();
    let _ = Command::new("pkill").arg("wireplumber").output();
    let _ = Command::new("pkill").arg("pipewire").output();
    
    std::thread::sleep(std::time::Duration::from_millis(500));
    
    let _ = Command::new("setsid")
        .arg("pipewire")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();

    let _ = Command::new("setsid")
        .arg("wireplumber")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();

    let _ = Command::new("setsid")
        .arg("pipewire-pulse")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();

    Ok(())
}

pub fn is_dsp_active() -> bool {
    let output = Command::new("pw-cli")
        .args(&["list-objects", "Module"])
        .output();
        
    if let Ok(out) = output {
        let text = String::from_utf8_lossy(&out.stdout);
        text.contains("libpipewire-module-filter-chain")
    } else {
        false
    }
}

