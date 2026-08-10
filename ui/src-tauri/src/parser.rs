use crate::dsp::{AudioOptimizerBand, DAX3Profile, MBCompressorBand, PEQBand};
use roxmltree::Document;
use std::collections::HashMap;
use std::fs;

fn float_elem(node: roxmltree::Node, tag_name: &str, default: f32) -> f32 {
    node.children()
        .find(|n| n.has_tag_name(tag_name))
        .and_then(|n| n.text())
        .and_then(|t| t.trim().parse::<f32>().ok())
        .unwrap_or(default)
}

fn bool_elem(node: roxmltree::Node, tag_name: &str, default: bool) -> bool {
    let val = float_elem(node, tag_name, if default { 1.0 } else { 0.0 });
    val > 0.0
}

pub fn parse_dax3_xml(filepath: &str) -> Result<Vec<DAX3Profile>, String> {
    let xml = fs::read_to_string(filepath).map_err(|e| e.to_string())?;
    let doc = Document::parse(&xml).map_err(|e| e.to_string())?;
    
    let root = doc.root_element();
    let tuning = root.children().find(|n| n.has_tag_name("tuning")).unwrap_or(root);

    let mut profiles = Vec::new();

    for endpoint in tuning.children().filter(|n| n.has_tag_name("endpoint")) {
        let endpoint_type = endpoint.attribute("type").unwrap_or("unknown");
        
        for profile_elem in endpoint.children().filter(|n| n.has_tag_name("profile")) {
            let profile_type = profile_elem.attribute("type").unwrap_or(endpoint_type);
            
            let mut profile = DAX3Profile {
                name: profile_type.to_string(),
                endpoint_type: endpoint_type.to_string(),
                peq_bands: Vec::new(),
                ao_bands: Vec::new(),
                mb_compressor: Vec::new(),
                volmax_boost: 0.0,
                ieq_enabled: false,
                ieq_amount: 0.0,
                ieq_curve: Vec::new(),
                dialog_enhancer: 0.0,
                volume_leveler: 0.0,
                surround_boost: 0.0,
                crossover_freqs: Vec::new(),
            };

            if let Some(cp) = profile_elem.children().find(|n| n.has_tag_name("tuning-cp")) {
                profile.ieq_enabled = bool_elem(cp, "ieq-enable", false);
                profile.ieq_amount = float_elem(cp, "ieq-amount", 0.0);
                profile.dialog_enhancer = float_elem(cp, "dialog-enhancer-amount", float_elem(cp, "dialog-enhancer", 0.0));
                profile.volume_leveler = float_elem(cp, "volume-leveler-amount", float_elem(cp, "volume-leveler", 0.0));
                profile.surround_boost = float_elem(cp, "surround-boost", 0.0);
                profile.volmax_boost = float_elem(cp, "volmax-boost", 0.0);
            }

            if let Some(vlldp) = profile_elem.children().find(|n| n.has_tag_name("tuning-vlldp")) {
                let v = float_elem(vlldp, "volmax-boost", 0.0);
                if v != 0.0 {
                    profile.volmax_boost = v;
                }
                
                // PEQ Parsing (Placeholder for now, just to show how it'd work)
                // We will just insert dummy peq bands for the parsing proof-of-concept
                if let Some(peq) = vlldp.children().find(|n| n.has_tag_name("peq-tuning")) {
                    for i in 1..=10 {
                        let f = float_elem(peq, &format!("band_{}_freq", i), -1.0);
                        if f > 0.0 {
                            profile.peq_bands.push(PEQBand {
                                filter_type: "peaking".to_string(),
                                freq: f,
                                gain: float_elem(peq, &format!("band_{}_gain", i), 0.0),
                                q: float_elem(peq, &format!("band_{}_q", i), 1.0),
                                enabled: true,
                            });
                        }
                    }
                }
            }

            profiles.push(profile);
        }
    }

    Ok(profiles)
}
