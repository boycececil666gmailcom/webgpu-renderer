struct FrameUniforms {
    view: mat4x4<f32>,
    projection: mat4x4<f32>,
    cam_pos: vec4<f32>,
    light_dir: vec4<f32>,
    light_color: vec4<f32>,
};

struct ObjectUniforms {
    model: mat4x4<f32>,
    normal_matrix: mat4x4<f32>,
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
@group(1) @binding(0) var<uniform> obj: ObjectUniforms;
@group(2) @binding(0) var<uniform> mat: MaterialUniforms;
@group(2) @binding(1) var mat_texture: texture_2d<f32>;
@group(2) @binding(2) var mat_sampler: sampler;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) tex_coords: vec2<f32>,
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
    let world_pos4 = obj.model * vec4<f32>(in.position, 1.0);
    out.world_pos = world_pos4.xyz;
    out.clip_position = frame.projection * frame.view * world_pos4;
    let n4 = obj.normal_matrix * vec4<f32>(in.normal, 0.0);
    out.normal = n4.xyz;
    out.tex_coords = in.tex_coords;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
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

    if (mat.is_unlit == 1u) {
        return base_color;
    }

    let norm = normalize(in.normal);
    let view_dir = normalize(frame.cam_pos.xyz - in.world_pos);
    let light_dir = normalize(frame.light_dir.xyz);
    let radiance = frame.light_color.rgb * frame.light_color.a;
    let half_dir = normalize(light_dir + view_dir);

    let n_dot_l = max(dot(norm, light_dir), 0.0);
    let n_dot_v = max(dot(norm, view_dir), 0.001);
    let n_dot_h = max(dot(norm, half_dir), 0.0);
    let v_dot_h = max(dot(view_dir, half_dir), 0.0);

    let f0 = mix(vec3<f32>(0.04), base_color.rgb, mat.metallic);
    let fresnel = f0 + (1.0 - f0) * pow(clamp(1.0 - v_dot_h, 0.0, 1.0), 5.0);

    let rough = max(mat.roughness, 0.04);
    let alpha = rough * rough;
    let alpha2 = alpha * alpha;
    let denom = (n_dot_h * n_dot_h * (alpha2 - 1.0) + 1.0);
    let d = alpha2 / (3.14159265 * denom * denom);

    let k = (rough + 1.0) * (rough + 1.0) / 8.0;
    let g1 = n_dot_v / (n_dot_v * (1.0 - k) + k);
    let g2 = n_dot_l / (n_dot_l * (1.0 - k) + k);
    let g = g1 * g2;

    let specular_brdf = (d * g * fresnel) / max(4.0 * n_dot_v * n_dot_l, 0.001);
    let kd = (vec3<f32>(1.0) - fresnel) * (1.0 - mat.metallic);
    let diffuse_brdf = kd * base_color.rgb / 3.14159265;

    var direct_light = (diffuse_brdf + specular_brdf) * n_dot_l * 3.14159265 * radiance;

    if (mat.clearcoat > 0.0) {
        let cc_rough = 0.1;
        let cc_alpha = cc_rough * cc_rough;
        let cc_alpha2 = cc_alpha * cc_alpha;
        let cc_denom = (n_dot_h * n_dot_h * (cc_alpha2 - 1.0) + 1.0);
        let cc_d = cc_alpha2 / (3.14159265 * cc_denom * cc_denom);
        let cc_fresnel = 0.04 + 0.96 * pow(clamp(1.0 - v_dot_h, 0.0, 1.0), 5.0);
        let cc_k = (cc_rough + 1.0) * (cc_rough + 1.0) / 8.0;
        let cc_g = (n_dot_v / (n_dot_v * (1.0 - cc_k) + cc_k)) * (n_dot_l / (n_dot_l * (1.0 - cc_k) + cc_k));
        let cc_spec = (cc_d * cc_g * cc_fresnel) / max(4.0 * n_dot_v * n_dot_l, 0.001);
        direct_light = direct_light * (1.0 - cc_fresnel * mat.clearcoat) + vec3<f32>(cc_spec * n_dot_l * mat.clearcoat) * radiance;
    }

    let ambient = vec3<f32>(0.04) * base_color.rgb;
    let final_color = ambient + direct_light;

    return vec4<f32>(final_color, base_color.a);
}
