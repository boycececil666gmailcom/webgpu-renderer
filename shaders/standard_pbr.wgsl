struct FrameUniforms {
    view: mat4x4<f32>,
    projection: mat4x4<f32>,
    cam_pos: vec4<f32>,
    sun_view_proj: mat4x4<f32>,
    sun_dir: vec4<f32>,
    sun_color: vec4<f32>,
};

struct MaterialUniforms {
    base_color: vec4<f32>,
    metallic: f32,
    roughness: f32,
    clearcoat: f32,
    alpha_cutoff: f32,
    use_texture: u32,
    is_unlit: u32,
    alpha_mode: u32,
    _padding: u32,
};

@group(0) @binding(0) var<uniform> frame: FrameUniforms;
@group(0) @binding(1) var env_map: texture_2d<f32>;
@group(0) @binding(2) var env_sampler: sampler;
@group(0) @binding(3) var shadow_map: texture_depth_2d;
@group(0) @binding(4) var shadow_sampler: sampler_comparison;

@group(1) @binding(0) var<uniform> mat: MaterialUniforms;
@group(1) @binding(1) var mat_texture: texture_2d<f32>;
@group(1) @binding(2) var mat_sampler: sampler;

fn sample_equirect(dir: vec3<f32>, lod: f32) -> vec3<f32> {
    let pi = 3.14159265;
    let u = atan2(dir.x, dir.z) / (2.0 * pi) + 0.5;
    let v = 0.5 - asin(clamp(dir.y, -1.0, 1.0)) / pi;
    return textureSampleLevel(env_map, env_sampler, vec2<f32>(u, v), lod).rgb;
}

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) tex_coords: vec2<f32>,
    @location(3) model_col0: vec4<f32>,
    @location(4) model_col1: vec4<f32>,
    @location(5) model_col2: vec4<f32>,
    @location(6) model_col3: vec4<f32>,
    @location(7) norm_col0: vec4<f32>,
    @location(8) norm_col1: vec4<f32>,
    @location(9) norm_col2: vec4<f32>,
    @location(10) norm_col3: vec4<f32>,
};

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) tex_coords: vec2<f32>,
    @location(2) world_pos: vec3<f32>,
};

@vertex
fn vs_main(in: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    let model = mat4x4<f32>(
        in.model_col0,
        in.model_col1,
        in.model_col2,
        in.model_col3,
    );
    let normal_matrix = mat4x4<f32>(
        in.norm_col0,
        in.norm_col1,
        in.norm_col2,
        in.norm_col3,
    );
    let world_pos4 = model * vec4<f32>(in.position, 1.0);
    out.world_pos = world_pos4.xyz;
    out.clip_position = frame.projection * frame.view * world_pos4;
    let n4 = normal_matrix * vec4<f32>(in.normal, 0.0);
    out.normal = n4.xyz;
    out.tex_coords = in.tex_coords;
    return out;
}

@vertex
fn vs_shadow(in: VertexInput) -> @builtin(position) vec4<f32> {
    let model = mat4x4<f32>(
        in.model_col0,
        in.model_col1,
        in.model_col2,
        in.model_col3,
    );
    let world_pos4 = model * vec4<f32>(in.position, 1.0);
    return frame.sun_view_proj * world_pos4;
}

struct ShadowMaskedOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) tex_coords: vec2<f32>,
};

@vertex
fn vs_shadow_masked(in: VertexInput) -> ShadowMaskedOutput {
    var out: ShadowMaskedOutput;
    let model = mat4x4<f32>(
        in.model_col0,
        in.model_col1,
        in.model_col2,
        in.model_col3,
    );
    let world_pos4 = model * vec4<f32>(in.position, 1.0);
    out.clip_position = frame.sun_view_proj * world_pos4;
    out.tex_coords = in.tex_coords;
    return out;
}

@fragment
fn fs_shadow_masked(in: ShadowMaskedOutput) {
    var base_color = mat.base_color;
    if (mat.use_texture == 1u) {
        base_color = base_color * textureSample(mat_texture, mat_sampler, in.tex_coords);
    }
    if (base_color.a < mat.alpha_cutoff) {
        discard;
    }
}

fn sample_shadow(world_pos: vec3<f32>, norm: vec3<f32>) -> f32 {
    let light_space_pos = frame.sun_view_proj * vec4<f32>(world_pos, 1.0);
    let proj_coords = light_space_pos.xyz / light_space_pos.w;
    let uv = proj_coords.xy * vec2<f32>(0.5, -0.5) + vec2<f32>(0.5, 0.5);
    let current_depth = proj_coords.z;

    if (uv.x < 0.001 || uv.x > 0.999 || uv.y < 0.001 || uv.y > 0.999 || current_depth > 1.0 || current_depth < 0.0) {
        return 1.0;
    }

    let n_dot_l = max(dot(norm, frame.sun_dir.xyz), 0.0);
    let bias = max(0.0035 * (1.0 - n_dot_l), 0.0006);

    var shadow = 0.0;
    let texel_size = vec2<f32>(1.0 / 2048.0, 1.0 / 2048.0);
    for (var x = -1; x <= 1; x++) {
        for (var y = -1; y <= 1; y++) {
            let offset = vec2<f32>(f32(x), f32(y)) * texel_size;
            shadow += textureSampleCompareLevel(
                shadow_map,
                shadow_sampler,
                uv + offset,
                current_depth - bias
            );
        }
    }
    return shadow / 9.0;
}

fn tone_map_aces(x: vec3<f32>) -> vec3<f32> {
    let a = 2.51;
    let b = 0.03;
    let c = 2.43;
    let d = 0.59;
    let e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), vec3<f32>(0.0), vec3<f32>(1.0));
}

fn evaluate_lighting(in: VertexOutput, is_front: bool, base_color: vec4<f32>) -> vec4<f32> {
    if (mat.is_unlit == 1u) {
        return base_color;
    }

    let pi = 3.14159265;
    var norm = normalize(in.normal);
    if (!is_front) {
        norm = -norm;
    }
    let view_dir = normalize(frame.cam_pos.xyz - in.world_pos);
    let n_dot_v = max(dot(norm, view_dir), 0.001);

    let f0 = mix(vec3<f32>(0.04), base_color.rgb, mat.metallic);
    let rough = max(mat.roughness, 0.04);

    let shadow = sample_shadow(in.world_pos, norm);

    // --- Image-Based Lighting (IBL) with Shadow Ambient Occlusion ---
    // Diffuse IBL: hemispherical irradiance filtered at top mip levels
    let diffuse_irradiance = sample_equirect(norm, 8.5);
    let kd_env = (vec3<f32>(1.0) - f0) * (1.0 - mat.metallic);
    // When in shadow, the sky hemisphere is partially occluded.
    // Foliage has a higher ambient floor (0.75) because tree canopies are porous and scatter light.
    let sky_floor = select(0.45, 0.75, mat.alpha_mode == 1u);
    let sky_occlusion = mix(sky_floor, 1.0, shadow);
    let diffuse_ibl = kd_env * diffuse_irradiance * base_color.rgb * 0.75 * sky_occlusion;

    // Specular IBL: prefiltered environment radiance filtered by roughness
    let reflect_dir = reflect(-view_dir, norm);
    let spec_lod = rough * 8.0;
    let prefiltered_spec = sample_equirect(reflect_dir, spec_lod);
    let f_env = f0 + (max(vec3<f32>(1.0 - rough), f0) - f0) * pow(clamp(1.0 - n_dot_v, 0.0, 1.0), 5.0);
    let specular_ibl = f_env * prefiltered_spec * mix(0.45, 1.0, shadow);

    var total_ibl = diffuse_ibl + specular_ibl;

    // Ground bounce lighting for downward-facing foliage and canopy undersides
    if (mat.alpha_mode == 1u) {
        let ground_bounce = base_color.rgb * vec3<f32>(0.22, 0.26, 0.15) * max(-norm.y, 0.0);
        total_ibl = total_ibl + ground_bounce;
    }

    // Clearcoat IBL: sharp specular reflection on top of base coat
    if (mat.clearcoat > 0.0) {
        let cc_fresnel_env = 0.04 + 0.96 * pow(clamp(1.0 - n_dot_v, 0.0, 1.0), 5.0);
        let cc_spec_env = sample_equirect(reflect_dir, 0.5);
        let cc_ibl = cc_spec_env * (cc_fresnel_env * mat.clearcoat);
        total_ibl = total_ibl * (1.0 - cc_fresnel_env * mat.clearcoat) + cc_ibl;
    }

    // --- Direct Directional Sun Lighting ---
    let l = normalize(frame.sun_dir.xyz);
    let h = normalize(view_dir + l);
    let n_dot_l = max(dot(norm, l), 0.0);
    let n_dot_h = max(dot(norm, h), 0.0);
    let v_dot_h = max(dot(view_dir, h), 0.0);

    // Direct Specular (GGX)
    let alpha_rough = rough * rough;
    let alpha2 = alpha_rough * alpha_rough;
    let denom_d = (n_dot_h * n_dot_h * (alpha2 - 1.0) + 1.0);
    let d = alpha2 / (pi * denom_d * denom_d);

    let k_direct = (rough + 1.0) * (rough + 1.0) / 8.0;
    let g_v = n_dot_v / (n_dot_v * (1.0 - k_direct) + k_direct);
    let g_l = n_dot_l / (n_dot_l * (1.0 - k_direct) + k_direct);
    let g = g_v * g_l;

    let f_direct = f0 + (1.0 - f0) * pow(clamp(1.0 - v_dot_h, 0.0, 1.0), 5.0);
    let spec_direct = (d * g * f_direct) / max(4.0 * n_dot_v * n_dot_l, 0.001);

    // Direct Diffuse (Lambert)
    let kd_direct = (vec3<f32>(1.0) - f_direct) * (1.0 - mat.metallic);
    let diff_direct = kd_direct * base_color.rgb / pi;

    // Foliage Subsurface Translucency (back-face light scatter penetrating the canopy)
    var foliage_translucency = vec3<f32>(0.0);
    if (mat.alpha_mode == 1u) {
        let back_sun = max(dot(-norm, l), 0.0);
        let trans_shadow = mix(0.40, 1.0, shadow);
        foliage_translucency = base_color.rgb * frame.sun_color.rgb * back_sun * 0.45 * trans_shadow;
    }

    let direct_color = (diff_direct + spec_direct) * frame.sun_color.rgb * n_dot_l * shadow
                     + foliage_translucency;

    var total_color = total_ibl + direct_color;

    // Clearcoat direct reflection
    if (mat.clearcoat > 0.0) {
        let cc_rough = 0.1;
        let cc_alpha = cc_rough * cc_rough;
        let cc_denom = (n_dot_h * n_dot_h * (cc_alpha * cc_alpha - 1.0) + 1.0);
        let cc_d = (cc_alpha * cc_alpha) / (pi * cc_denom * cc_denom);
        let cc_f = 0.04 + 0.96 * pow(clamp(1.0 - v_dot_h, 0.0, 1.0), 5.0);
        let cc_spec = (cc_d * cc_f * mat.clearcoat) / max(4.0 * n_dot_v * n_dot_l, 0.001);
        total_color = total_color + cc_spec * frame.sun_color.rgb * n_dot_l * shadow;
    }

    // ACES Filmic Tone Mapping with exposure calibration
    let exposure = 1.15;
    let mapped = tone_map_aces(total_color * exposure);

    return vec4<f32>(mapped, base_color.a);
}

// Full Early-Z with immediate hardware depth writes (ZERO discard instructions)
@fragment
fn fs_opaque(in: VertexOutput, @builtin(front_facing) is_front: bool) -> @location(0) vec4<f32> {
    var base_color = mat.base_color;
    if (mat.use_texture == 1u) {
        base_color = base_color * textureSample(mat_texture, mat_sampler, in.tex_coords);
    }
    base_color.a = 1.0;
    return evaluate_lighting(in, is_front, base_color);
}

// Alpha-tested foliage / cutout (evaluated after solid opaque has primed Z-buffer)
@fragment
fn fs_masked(in: VertexOutput, @builtin(front_facing) is_front: bool) -> @location(0) vec4<f32> {
    var base_color = mat.base_color;
    if (mat.use_texture == 1u) {
        base_color = base_color * textureSample(mat_texture, mat_sampler, in.tex_coords);
    }
    if (base_color.a < mat.alpha_cutoff) {
        discard;
    }
    base_color.a = 1.0;
    return evaluate_lighting(in, is_front, base_color);
}

// Alpha-blended transparent materials (rendered back-to-front with depth write disabled)
@fragment
fn fs_transparent(in: VertexOutput, @builtin(front_facing) is_front: bool) -> @location(0) vec4<f32> {
    var base_color = mat.base_color;
    if (mat.use_texture == 1u) {
        base_color = base_color * textureSample(mat_texture, mat_sampler, in.tex_coords);
    }
    return evaluate_lighting(in, is_front, base_color);
}

@fragment
fn fs_main(in: VertexOutput, @builtin(front_facing) is_front: bool) -> @location(0) vec4<f32> {
    var base_color = mat.base_color;
    if (mat.use_texture == 1u) {
        base_color = base_color * textureSample(mat_texture, mat_sampler, in.tex_coords);
    }

    if (mat.alpha_mode == 0u) {
        base_color.a = 1.0;
    } else if (mat.alpha_mode == 1u) {
        if (base_color.a < mat.alpha_cutoff) {
            discard;
        }
        base_color.a = 1.0;
    }

    return evaluate_lighting(in, is_front, base_color);
}
