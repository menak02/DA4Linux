use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PEQBand {
    pub filter_type: String,
    pub freq: f32,
    pub gain: f32,
    pub q: f32,
    pub enabled: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MBCompressorBand {
    pub threshold: f32,
    pub ratio: f32,
    pub attack: f32,
    pub release: f32,
    pub knee: f32,
    pub makeup_gain: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AudioOptimizerBand {
    pub gains: Vec<f32>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DAX3Profile {
    pub name: String,
    pub endpoint_type: String,
    pub peq_bands: Vec<PEQBand>,
    pub ao_bands: Vec<AudioOptimizerBand>,
    pub mb_compressor: Vec<MBCompressorBand>,
    pub volmax_boost: f32,
    pub ieq_enabled: bool,
    pub ieq_amount: f32,
    pub ieq_curve: Vec<f32>,
    pub dialog_enhancer: f32,
    pub volume_leveler: f32,
    pub surround_boost: f32,
    pub crossover_freqs: Vec<f32>,
}
