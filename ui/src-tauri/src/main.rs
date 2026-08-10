// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // Ensure GTK prefers Wayland but falls back to X11 seamlessly
    std::env::set_var("GDK_BACKEND", "wayland,x11");

    if std::path::Path::new("/sys/module/nvidia").exists() {
        // Fix Wayland protocol Error 71 (Explicit Sync) on NVIDIA
        std::env::set_var("__NV_DISABLE_EXPLICIT_SYNC", "1");
        
        // Disable the DMABUF renderer on NVIDIA drivers. 
        // Note: This is NOT a software rendering fallback. OpenGL compositing 
        // remains fully hardware accelerated. This is the official upstream 
        // WebKitGTK fix for NVIDIA's GBM implementation bugs.
        std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
    
    da4linux_lib::run()
}
