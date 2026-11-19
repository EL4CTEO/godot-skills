# Networking patterns (compiled by the test suite)

## Lobby autoload: host/join over ENet, player registry, clean disconnects
```gdscript
extends Node

signal player_joined(id: int, info: Dictionary)
signal player_left(id: int)
signal connection_lost

const PORT := 7000
const MAX_CLIENTS := 8

var players: Dictionary[int, Dictionary] = {}
var local_info := {"name": "Player"}


func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(func() -> void: players[multiplayer.get_unique_id()] = local_info)
	multiplayer.connection_failed.connect(_reset)
	multiplayer.server_disconnected.connect(func() -> void:
		_reset()
		connection_lost.emit())


func host() -> Error:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_server(PORT, MAX_CLIENTS)
	if err != OK:
		return err
	multiplayer.multiplayer_peer = peer
	players[1] = local_info
	return OK


func join(address: String) -> Error:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_client(address, PORT)
	if err == OK:
		multiplayer.multiplayer_peer = peer
	return err


func _on_peer_connected(id: int) -> void:
	_register.rpc_id(id, local_info)  # tell the newcomer who we are


@rpc("any_peer", "reliable")
func _register(info: Dictionary) -> void:
	var id := multiplayer.get_remote_sender_id()
	var safe_name := str(info.get("name", "Player")).left(24)  # never trust peer data
	players[id] = {"name": safe_name}
	player_joined.emit(id, players[id])


func _on_peer_disconnected(id: int) -> void:
	players.erase(id)
	player_left.emit(id)


func _reset() -> void:
	multiplayer.multiplayer_peer = null
	players.clear()
```

## Server spawns players; each client owns only its input
```gdscript
extends Node3D

@export var player_scene: PackedScene

@onready var spawner: MultiplayerSpawner = $MultiplayerSpawner
@onready var players_root: Node3D = $Players


func _ready() -> void:
	spawner.spawn_path = players_root.get_path()
	spawner.add_spawnable_scene(player_scene.resource_path)
	if not multiplayer.is_server():
		return
	multiplayer.peer_connected.connect(_spawn_player)
	multiplayer.peer_disconnected.connect(_despawn_player)
	_spawn_player(1)  # listen-server host
	for id in multiplayer.get_peers():
		_spawn_player(id)


func _spawn_player(id: int) -> void:
	var p := player_scene.instantiate()
	p.name = str(id)  # same node path on every peer
	players_root.add_child(p, true)


func _despawn_player(id: int) -> void:
	var p := players_root.get_node_or_null(str(id))
	if p:
		p.queue_free()
```

## Player: input synchronized from its owner, state from the server
```gdscript
extends CharacterBody3D

## Child "InputSync" (MultiplayerSynchronizer) replicates `move_input` and is owned by the client.
## Child "StateSync" replicates position/velocity and stays owned by the server.

@export var speed := 6.0
var move_input := Vector2.ZERO


func _enter_tree() -> void:
	$InputSync.set_multiplayer_authority(int(name))


func _physics_process(delta: float) -> void:
	if $InputSync.is_multiplayer_authority():
		move_input = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if not multiplayer.is_server():
		return
	var dir := Vector3(move_input.x, 0, move_input.y).limit_length(1.0)
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	if not is_on_floor():
		velocity += get_gravity() * delta
	move_and_slide()


@rpc("any_peer", "call_local", "reliable")
func request_interact(target_path: NodePath) -> void:
	if not multiplayer.is_server():
		return
	var sender := multiplayer.get_remote_sender_id()
	if sender != 0 and sender != int(name):  # 0 = called locally on the server
		return
	var target := get_node_or_null(target_path) as Node3D
	if target and target.global_position.distance_to(global_position) < 3.0 and target.has_method(&"interact"):
		target.call(&"interact", self)
```

## Interpolating remote entities (render side)
```gdscript
extends Node3D

## Server-synced target transform arrives in `net_position`; the visual child chases it.
@export var smoothing := 15.0
var net_position := Vector3.ZERO

@onready var visual: Node3D = $Visual


func _process(delta: float) -> void:
	if multiplayer.is_server():
		visual.position = Vector3.ZERO
		return
	var target := net_position - global_position
	visual.position = visual.position.lerp(target, 1.0 - exp(-smoothing * delta))
```

## HTTP JSON request with timeout and error handling
```gdscript
extends Node

signal leaderboard_loaded(entries: Array)

@onready var http := HTTPRequest.new()


func _ready() -> void:
	http.timeout = 10.0
	add_child(http)
	http.request_completed.connect(_on_completed)


func fetch(url: String) -> void:
	var err := http.request(url, ["Accept: application/json"])
	if err != OK:
		push_error("request failed to start: %s" % error_string(err))


func _on_completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code >= 400:
		push_warning("leaderboard: result %d http %d" % [result, code])
		return
	var data: Variant = JSON.parse_string(body.get_string_from_utf8())
	if data is Dictionary and data.get("entries") is Array:
		leaderboard_loaded.emit(data["entries"])
```

## C# RPCs with attributes
```csharp
using Godot;

public partial class Weapon : Node3D
{
    [Rpc(MultiplayerApi.RpcMode.AnyPeer, CallLocal = true, TransferMode = MultiplayerPeer.TransferModeEnum.Reliable)]
    public void RequestFire(Vector3 direction)
    {
        if (!Multiplayer.IsServer())
            return;
        long sender = Multiplayer.GetRemoteSenderId();
        if (sender != 0 && sender != GetMultiplayerAuthority())
            return; // only the owner may fire this weapon
        Rpc(MethodName.PlayFireEffects, direction.Normalized());
    }

    [Rpc(MultiplayerApi.RpcMode.Authority, CallLocal = true, TransferMode = MultiplayerPeer.TransferModeEnum.Unreliable)]
    public void PlayFireEffects(Vector3 direction) => GD.Print("bang ", direction);

    public void Fire(Vector3 direction) => RpcId(1, MethodName.RequestFire, direction);
}
```
