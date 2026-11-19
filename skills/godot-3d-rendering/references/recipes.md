# 3D recipes (compiled by the test suite)

Build lighting in the editor whenever possible. These scripts are for procedural setups, runtime quality settings and tools.

## Outdoor environment from code (AgX, sky, sun, fog, Forward+ extras guarded)
```gdscript
extends Node3D

@export var sun_energy := 1.2


func _ready() -> void:
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.35, 0.55, 0.9)
	sky_mat.ground_bottom_color = Color(0.2, 0.17, 0.13)
	var sky := Sky.new()
	sky.sky_material = sky_mat

	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.glow_enabled = true
	env.fog_enabled = true
	env.fog_density = 0.002
	if _is_forward_plus():
		env.ssao_enabled = true
		env.sdfgi_enabled = true
		env.volumetric_fog_enabled = true
		env.volumetric_fog_density = 0.01

	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = sun_energy
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 150.0
	add_child(sun)


func _is_forward_plus() -> bool:
	return RenderingServer.get_current_rendering_method() == "forward_plus"
```

## Day/night cycle (rotate the sun, tint and dim it)
```gdscript
extends DirectionalLight3D

@export var day_length_seconds := 600.0
@export var light_color_by_time: Gradient

var time_of_day := 0.3  # 0 = midnight, 0.5 = noon


func _process(delta: float) -> void:
	time_of_day = fposmod(time_of_day + delta / day_length_seconds, 1.0)
	rotation.x = -TAU * (time_of_day - 0.25)  # sunrise at 0.25
	var height := sin(TAU * (time_of_day - 0.25))
	light_energy = clampf(height * 1.5, 0.0, 1.5)
	visible = height > -0.05
	if light_color_by_time:
		light_color = light_color_by_time.sample(time_of_day)
```

## Materials from code (unique per instance, ORM, transparency, stencil outline)
```gdscript
extends MeshInstance3D

@export var albedo: Texture2D
@export var orm: Texture2D
@export var normal: Texture2D


func _ready() -> void:
	var mat := ORMMaterial3D.new()
	mat.albedo_texture = albedo
	mat.orm_texture = orm
	mat.normal_enabled = normal != null
	mat.normal_texture = normal
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	mat.alpha_scissor_threshold = 0.5
	set_surface_override_material(0, mat)


func set_highlight(on: bool) -> void:
	var mat := get_surface_override_material(0) as BaseMaterial3D
	if mat:
		mat.stencil_mode = BaseMaterial3D.STENCIL_MODE_OUTLINE if on else BaseMaterial3D.STENCIL_MODE_DISABLED
		mat.stencil_color = Color(1.0, 0.8, 0.1)
```

## Runtime graphics settings (quality presets, scaling, AA, HDR)
```gdscript
extends Node

enum Quality { LOW, MEDIUM, HIGH }


func apply(quality: Quality, hdr: bool) -> void:
	var vp := get_viewport()
	match quality:
		Quality.LOW:
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR
			vp.scaling_3d_scale = 0.67
			vp.msaa_3d = Viewport.MSAA_DISABLED
			vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
			vp.mesh_lod_threshold = 4.0
		Quality.MEDIUM:
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
			vp.scaling_3d_scale = 1.0
			vp.msaa_3d = Viewport.MSAA_2X
			vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_SMAA
			vp.mesh_lod_threshold = 2.0
		Quality.HIGH:
			vp.scaling_3d_scale = 1.0
			vp.msaa_3d = Viewport.MSAA_4X
			vp.use_taa = RenderingServer.get_current_rendering_method() == "forward_plus"
			vp.mesh_lod_threshold = 1.0
	var win := get_window()
	win.hdr_output_requested = hdr and DisplayServer.window_is_hdr_output_supported(win.get_window_id())
```
```csharp
using Godot;

public partial class GraphicsSettings : Node
{
    public void ApplyHigh(bool hdr)
    {
        Viewport vp = GetViewport();
        vp.Scaling3DScale = 1.0f;
        vp.Msaa3D = Viewport.Msaa.Msaa4X;
        vp.UseTaa = RenderingServer.GetCurrentRenderingMethod() == "forward_plus";
        Window win = GetWindow();
        win.HdrOutputRequested = hdr && DisplayServer.WindowIsHdrOutputSupported(win.GetWindowId());
    }
}
```

## Visibility ranges (HLOD) and far-prop culling
```gdscript
extends Node3D

@export var detail_end := 60.0
@export var impostor: GeometryInstance3D


func _ready() -> void:
	for child in find_children("*", "GeometryInstance3D", true, false):
		var g := child as GeometryInstance3D
		if g == impostor:
			continue
		g.visibility_range_end = detail_end
		g.visibility_range_end_margin = 5.0
		g.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	if impostor:
		impostor.visibility_range_begin = detail_end
		impostor.visibility_range_begin_margin = 5.0
```
