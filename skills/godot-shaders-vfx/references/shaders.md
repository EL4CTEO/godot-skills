# Shader library (each block is a full .gdshader, validated by shader_check in the tests)

## Dissolve with glowing edge (spatial)
```gdshader
shader_type spatial;

uniform sampler2D albedo_tex : source_color, hint_default_white;
uniform sampler2D noise_tex : hint_default_white;
uniform float progress : hint_range(0.0, 1.0) = 0.0;
uniform float edge_width : hint_range(0.0, 0.2) = 0.05;
uniform vec4 edge_color : source_color = vec4(1.0, 0.45, 0.1, 1.0);
uniform float edge_energy : hint_range(0.0, 16.0) = 4.0;

void fragment() {
	float n = texture(noise_tex, UV).r;
	if (n < progress) {
		discard;
	}
	ALBEDO = texture(albedo_tex, UV).rgb;
	float edge = 1.0 - smoothstep(0.0, edge_width, n - progress);
	EMISSION = edge_color.rgb * edge * edge_energy;
}
```

## Hit flash per instance (no material duplication)
```gdshader
shader_type spatial;

uniform sampler2D albedo_tex : source_color, hint_default_white;
instance uniform float flash : hint_range(0.0, 1.0) = 0.0;
instance uniform vec4 flash_color : source_color = vec4(1.0);

void fragment() {
	vec3 base = texture(albedo_tex, UV).rgb;
	ALBEDO = mix(base, flash_color.rgb, flash);
	EMISSION = flash_color.rgb * flash * 2.0;
}
```

## 2D sprite outline + hit flash (canvas_item)
```gdshader
shader_type canvas_item;

uniform vec4 outline_color : source_color = vec4(0.0, 0.0, 0.0, 1.0);
uniform float outline_px : hint_range(0.0, 8.0, 1.0) = 1.0;
uniform float flash : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	vec2 px = TEXTURE_PIXEL_SIZE * outline_px;
	float a = texture(TEXTURE, UV + vec2(px.x, 0.0)).a + texture(TEXTURE, UV - vec2(px.x, 0.0)).a
			+ texture(TEXTURE, UV + vec2(0.0, px.y)).a + texture(TEXTURE, UV - vec2(0.0, px.y)).a;
	vec4 outlined = mix(vec4(outline_color.rgb, min(a, 1.0) * outline_color.a), c, c.a);
	COLOR = vec4(mix(outlined.rgb, vec3(1.0), flash * c.a), outlined.a);
}
```

## Water: scrolling normals, depth fade, fresnel (Forward+ / Mobile)
```gdshader
shader_type spatial;
render_mode cull_disabled;

uniform vec4 shallow : source_color = vec4(0.2, 0.7, 0.8, 0.6);
uniform vec4 deep : source_color = vec4(0.02, 0.15, 0.3, 0.95);
uniform sampler2D normal_a : hint_normal;
uniform sampler2D normal_b : hint_normal;
uniform sampler2D depth_tex : hint_depth_texture, filter_linear_mipmap;
uniform float depth_fade : hint_range(0.1, 10.0) = 2.5;
uniform vec2 flow = vec2(0.03, 0.02);

void fragment() {
	vec3 na = texture(normal_a, UV * 4.0 + flow * TIME).rgb;
	vec3 nb = texture(normal_b, UV * 6.0 - flow * TIME * 0.7).rgb;
	NORMAL_MAP = normalize(na + nb - 1.0);
	float scene_depth = texture(depth_tex, SCREEN_UV).r;
	vec4 world = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, scene_depth, 1.0);
	float dist = -world.z / world.w + VERTEX.z;
	float t = clamp(dist / depth_fade, 0.0, 1.0);
	vec4 col = mix(shallow, deep, t);
	float fresnel = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = col.rgb + fresnel * 0.2;
	ALPHA = clamp(col.a + fresnel * 0.3, 0.0, 1.0);
	ROUGHNESS = 0.05;
	SPECULAR = 0.6;
}
```

## Toon lighting with a custom light() function
```gdshader
shader_type spatial;
render_mode diffuse_toon, specular_toon;

uniform vec4 base_color : source_color = vec4(0.8, 0.5, 0.4, 1.0);
uniform int bands : hint_range(1, 6) = 3;
uniform float rim_amount : hint_range(0.0, 1.0) = 0.3;

void fragment() {
	ALBEDO = base_color.rgb;
}

void light() {
	float ndotl = clamp(dot(NORMAL, LIGHT), 0.0, 1.0);
	float stepped = floor(ndotl * float(bands)) / float(bands);
	DIFFUSE_LIGHT += stepped * ATTENUATION * LIGHT_COLOR / PI;
	float rim = smoothstep(1.0 - rim_amount, 1.0, 1.0 - dot(NORMAL, VIEW)) * ndotl;
	DIFFUSE_LIGHT += rim * LIGHT_COLOR * 0.5;
}
```

## Foliage wind sway driven by a global uniform
Declare `wind_strength` (float) in Project Settings → Shader Globals first; it then works in every material.
```gdshader
shader_type spatial;
render_mode cull_disabled;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform float alpha_cutoff : hint_range(0.0, 1.0) = 0.5;
uniform float sway : hint_range(0.0, 1.0) = 0.15;

void vertex() {
	vec3 world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float h = clamp(VERTEX.y, 0.0, 1.0);  // anchor the base
	VERTEX.x += sin(TIME * 1.7 + world.x * 0.4 + world.z * 0.3) * sway * h;
}

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	ALBEDO = c.rgb;
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cutoff;
}
```

## Full-screen vignette + chromatic aberration (ColorRect on a CanvasLayer)
```gdshader
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float vignette : hint_range(0.0, 1.0) = 0.35;
uniform float aberration : hint_range(0.0, 0.02) = 0.003;

void fragment() {
	vec2 dir = SCREEN_UV - 0.5;
	vec3 c;
	c.r = texture(screen_tex, SCREEN_UV + dir * aberration).r;
	c.g = texture(screen_tex, SCREEN_UV).g;
	c.b = texture(screen_tex, SCREEN_UV - dir * aberration).b;
	float v = 1.0 - smoothstep(0.4, 0.9, length(dir) * (1.0 + vignette));
	COLOR = vec4(c * mix(1.0, v, vignette * 2.0), 1.0);
}
```

## Stencil x-ray: mask writer + revealed silhouette (4.5+)
```gdshader
shader_type spatial;
render_mode unshaded, depth_draw_never;
stencil_mode write, compare_always, 1;

void fragment() {
	ALBEDO = vec3(0.0);
	ALPHA = 0.0;
}
```
```gdshader
shader_type spatial;
render_mode unshaded, depth_test_disabled;
stencil_mode read, compare_equal, 1;

uniform vec4 silhouette : source_color = vec4(0.3, 0.8, 1.0, 0.6);

void fragment() {
	ALBEDO = silhouette.rgb;
	ALPHA = silhouette.a;
}
```

## Custom particle process shader (spiral emitter)
```gdshader
shader_type particles;

uniform float radius = 1.0;
uniform float rise_speed = 1.5;
uniform float spin = 3.0;

void start() {
	float a = float(INDEX) * 0.618 * 6.2831853;
	TRANSFORM[3].xyz = EMISSION_TRANSFORM[3].xyz + vec3(cos(a), 0.0, sin(a)) * radius;
	CUSTOM.x = a;
	VELOCITY = vec3(0.0, rise_speed, 0.0);
}

void process() {
	CUSTOM.x += spin * DELTA;
	vec3 center = EMISSION_TRANSFORM[3].xyz;
	TRANSFORM[3].x = center.x + cos(CUSTOM.x) * radius;
	TRANSFORM[3].z = center.z + sin(CUSTOM.x) * radius;
	COLOR.a = 1.0 - LIFETIME;
}
```
