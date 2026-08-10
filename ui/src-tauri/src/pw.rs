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
