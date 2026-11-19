# VFX scripts (compiled by the test suite)

## One-shot impact burst that cleans itself up
```gdscript
class_name ImpactBurst
extends GPUParticles3D


static func spawn(parent: Node, at: Vector3, normal: Vector3, packed: PackedScene) -> void:
	var fx := packed.instantiate() as GPUParticles3D
	parent.add_child(fx)
	fx.global_position = at
	if not normal.is_equal_approx(Vector3.UP) and not normal.is_equal_approx(Vector3.DOWN):
		fx.look_at(at + normal, Vector3.UP)
	fx.one_shot = true
	fx.explosiveness = 1.0
	fx.emitting = true
	fx.finished.connect(fx.queue_free)
```

## Hit flash driver for the instance-uniform shader
```gdscript
extends GeometryInstance3D

@export var flash_time := 0.12

var _tween: Tween


func flash(color := Color.WHITE) -> void:
	set_instance_shader_parameter(&"flash_color", color)
	if _tween:
		_tween.kill()
	_tween = create_tween()
	_tween.tween_method(func(v: float) -> void: set_instance_shader_parameter(&"flash", v), 1.0, 0.0, flash_time)
```

## Particles spawned at arbitrary points (bullet impacts) from one emitter
```gdscript
extends GPUParticles3D


func _ready() -> void:
	emitting = true
	amount_ratio = 0.0  # emitter stays alive; emit_particle() spawns on demand


func impact(at: Vector3, normal: Vector3) -> void:
	var xform := Transform3D(Basis.IDENTITY, at)
	for i in 6:
		var vel := (normal + Vector3(randf_range(-0.5, 0.5), randf_range(-0.5, 0.5), randf_range(-0.5, 0.5))) * 4.0
		emit_particle(xform, vel, Color.WHITE, Color.BLACK,
				GPUParticles3D.EMIT_FLAG_POSITION | GPUParticles3D.EMIT_FLAG_VELOCITY)
```

## Compositor effect skeleton (compute post-process, Forward+/Mobile, experimental API)
```gdscript
@tool
class_name GrayscaleEffect
extends CompositorEffect

var rd: RenderingDevice
var shader: RID
var pipeline: RID


func _init() -> void:
	effect_callback_type = EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
	rd = RenderingServer.get_rendering_device()
	RenderingServer.call_on_render_thread(_init_compute)


func _init_compute() -> void:
	if rd == null:
		return
	var src := RDShaderSource.new()
	src.language = RenderingDevice.SHADER_LANGUAGE_GLSL
	src.source_compute = """
#version 450
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
layout(rgba16f, set = 0, binding = 0) uniform image2D color_image;
layout(push_constant, std430) uniform Params { vec2 size; vec2 pad; } params;
void main() {
	ivec2 uv = ivec2(gl_GlobalInvocationID.xy);
	if (uv.x >= int(params.size.x) || uv.y >= int(params.size.y)) return;
	vec4 c = imageLoad(color_image, uv);
	float g = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
	imageStore(color_image, uv, vec4(vec3(g), c.a));
}
"""
	var spirv := rd.shader_compile_spirv_from_source(src)
	if not spirv.compile_error_compute.is_empty():
		push_error(spirv.compile_error_compute)
		return
	shader = rd.shader_create_from_spirv(spirv)
	pipeline = rd.compute_pipeline_create(shader)


func _render_callback(callback_type: int, render_data: RenderData) -> void:
	if rd == null or not pipeline.is_valid() or callback_type != EFFECT_CALLBACK_TYPE_POST_TRANSPARENT:
		return
	var buffers := render_data.get_render_scene_buffers() as RenderSceneBuffersRD
	if buffers == null:
		return
	var size := buffers.get_internal_size()
	var push := PackedFloat32Array([size.x, size.y, 0.0, 0.0]).to_byte_array()
	for view in buffers.get_view_count():
		var image := buffers.get_color_layer(view)
		var uniform := RDUniform.new()
		uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
		uniform.binding = 0
		uniform.add_id(image)
		var set := UniformSetCacheRD.get_cache(shader, 0, [uniform])
		var list := rd.compute_list_begin()
		rd.compute_list_bind_compute_pipeline(list, pipeline)
		rd.compute_list_bind_uniform_set(list, set, 0)
		rd.compute_list_set_push_constant(list, push, push.size())
		rd.compute_list_dispatch(list, (size.x - 1) / 8 + 1, (size.y - 1) / 8 + 1, 1)
		rd.compute_list_end()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and shader.is_valid() and rd:
		rd.free_rid(shader)  # also frees the pipeline
```
Attach it: `camera.compositor = Compositor.new()` then `camera.compositor.compositor_effects = [GrayscaleEffect.new()]` (or assign in the inspector on Camera3D/WorldEnvironment).
