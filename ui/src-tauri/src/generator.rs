use crate::dsp::{DAX3Profile, PEQBand};

pub fn generate_filter_graph(profile: &DAX3Profile, _limiter_type: &str) -> String {
    let mut peq_filters = Vec::new();
    for band in &profile.peq_bands {
        if band.enabled && band.gain != 0.0 {
            peq_filters.push(format!(
                "{{ type = {} freq = {:.1} gain = {:.3} q = {:.4} }}",
                band.filter_type, band.freq, band.gain, band.q
            ));
        }
    }

    let filters_str = if peq_filters.is_empty() {
        "{ type = bq_peaking freq = 1000 gain = 0.0 q = 0.707 }".to_string()
    } else {
        peq_filters.join(" ")
    };

    let volmax_db = if profile.volmax_boost > 0.0 { profile.volmax_boost / 16.0 } else { 0.0 };
    let volmax_linear = 10.0_f32.powf(volmax_db / 20.0);

    format!(
        r#"                    {{
                        type = builtin
                        name = peq
                        label = param_eq
                        config = {{
                            filters = [
                                {filters_str}
                            ]
                        }}
                    }}
                    {{
                        type = builtin
                        name = gain_out_l
                        label = linear
                        control = {{ "Mult" = {volmax_linear:.6} "Add" = 0.0 }}
                    }}
                    {{
                        type = builtin
                        name = gain_out_r
                        label = linear
                        control = {{ "Mult" = {volmax_linear:.6} "Add" = 0.0 }}
                    }}"#
    )
}
