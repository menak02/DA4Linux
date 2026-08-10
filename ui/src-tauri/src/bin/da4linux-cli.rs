use clap::{Parser, Subcommand};
use da4linux_lib::dsp::DAX3Profile;

// Note: To use the lib components from the binary, we need to export them in lib.rs.
// I will update lib.rs to make `dsp`, `generator`, `pw`, `parser` public.
// But we can assume it will be done.
use da4linux_lib::{parser, pw};
use std::fs;

#[derive(Parser)]
#[command(name = "da4linux")]
#[command(about = "DA4Linux DSP Engine CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Parse DAX3 XML and output JSON
    Parse {
        #[arg(long)]
        json: bool,
        
        /// Path to the XML file
        filepath: String,
    },
    /// Generate DSP Config
    Generate {
        #[arg(long)]
        json_profile: String,
        
        #[arg(long)]
        stages: Option<String>,
    },
    /// Detect plugins
    DetectPlugins,
}

fn main() {
    let cli = Cli::parse();

    match &cli.command {
        Commands::Parse { json, filepath } => {
            match parser::parse_dax3_xml(filepath) {
                Ok(profiles) => {
                    if *json {
                        println!("{}", serde_json::to_string_pretty(&profiles).unwrap());
                    } else {
                        println!("Found {} profiles.", profiles.len());
                        for p in profiles {
                            println!(" - {}", p.name);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Error parsing XML: {}", e);
                    std::process::exit(1);
                }
            }
        }
        Commands::Generate { json_profile, stages: _ } => {
            // Apply DSP profile directly
            if let Ok(profile) = serde_json::from_str::<DAX3Profile>(json_profile) {
                if let Err(e) = pw::apply_dsp_profile(&profile) {
                    eprintln!("Failed to apply DSP: {}", e);
                    std::process::exit(1);
                }
                println!("Successfully applied DSP to PipeWire.");
            } else {
                eprintln!("Failed to deserialize profile JSON.");
                std::process::exit(1);
            }
        }
        Commands::DetectPlugins => {
            let plugins = pw::detect_plugins();
            println!("{}", serde_json::to_string(&plugins).unwrap());
        }
    }
}
