"""
Mini-DSL Python -> JSON Scratch 3 (project.json).
Permet d'écrire les scripts Scratch en Python puis d'assembler un .sb3 valide.
"""
import hashlib
import json
import zipfile

_counter = [0]


def _nid(prefix="b"):
    _counter[0] += 1
    return f"{prefix}{_counter[0]}"


# ---------------------------------------------------------------- valeurs

class Var:
    def __init__(self, name):
        self.name = name


class ListRef:
    def __init__(self, name):
        self.name = name


class Arg:
    """Argument d'un bloc personnalisé (reporter)."""
    def __init__(self, name):
        self.name = name


class Blk:
    def __init__(self, opcode, inputs=None, fields=None, mutation=None, shadow=False):
        self.opcode = opcode
        self.inputs = inputs or {}
        self.fields = fields or {}
        self.mutation = mutation
        self.shadow = shadow


BOOL_OPCODES = {
    "operator_lt", "operator_gt", "operator_equals", "operator_and", "operator_or",
    "operator_not", "operator_contains", "sensing_touchingobject", "sensing_keypressed",
    "sensing_mousedown", "data_listcontainsitem", "sensing_touchingcolor",
    "argument_reporter_boolean",
}

TEXT_INPUTS = {"STRING", "STRING1", "STRING2", "MESSAGE", "ITEM", "LETTER", "COSTUME", "BACKDROP"}


# ---------------------------------------------------------------- cible

class Target:
    def __init__(self, name, is_stage=False):
        self.name = name
        self.is_stage = is_stage
        self.blocks = {}
        self.variables = {}   # name -> (id, value)
        self.lists = {}       # name -> (id, values)
        self.costumes = []
        self.sounds = []
        self.scripts = []
        self.x = 0
        self.y = 0
        self.size = 100
        self.direction = 90
        self.visible = True
        self.draggable = False
        self.rotation_style = "all around"
        self.layer = 1
        self.current_costume = 0
        self.volume = 100
        self.project = None
        self._script_y = 0

    # variables
    def add_var(self, name, value=0):
        self.variables[name] = (_nid("v"), value)

    def add_list(self, name, values=None):
        self.lists[name] = (_nid("l"), list(values or []))

    def add_costume(self, name, svg, cx, cy):
        data = svg.encode("utf-8")
        md5 = hashlib.md5(data).hexdigest()
        self.costumes.append({
            "name": name, "bitmapResolution": 1, "dataFormat": "svg",
            "assetId": md5, "md5ext": md5 + ".svg",
            "rotationCenterX": cx, "rotationCenterY": cy, "_data": data,
        })

    def add_sound(self, name, wav_bytes, rate, sample_count):
        md5 = hashlib.md5(wav_bytes).hexdigest()
        self.sounds.append({
            "name": name, "assetId": md5, "dataFormat": "wav", "format": "",
            "rate": rate, "sampleCount": sample_count, "md5ext": md5 + ".wav", "_data": wav_bytes,
        })

    def script(self, *blocks):
        """Ajoute un script (liste de Blk) à la cible."""
        flat = []
        for b in blocks:
            if isinstance(b, list):
                flat.extend(b)
            else:
                flat.append(b)
        self.scripts.append(flat)

    # ---- résolution des variables (locale puis globale)
    def _var_id(self, name):
        if name in self.variables:
            return self.variables[name][0]
        st = self.project.stage
        if name in st.variables:
            return st.variables[name][0]
        raise KeyError(f"variable inconnue: {name} (cible {self.name})")

    def _list_id(self, name):
        if name in self.lists:
            return self.lists[name][0]
        st = self.project.stage
        if name in st.lists:
            return st.lists[name][0]
        raise KeyError(f"liste inconnue: {name} (cible {self.name})")

    # ---- sérialisation des blocs
    def _emit_value(self, name, val, parent_id):
        """Retourne la représentation input pour une valeur."""
        if isinstance(val, bool):
            raise TypeError("bool interdit comme valeur")
        if isinstance(val, (int, float)):
            return [1, [4, str(val)]]
        if isinstance(val, str):
            if name in TEXT_INPUTS:
                return [1, [10, val]]
            return [1, [10, val]]
        if isinstance(val, Var):
            return [3, [12, val.name, self._var_id(val.name)], [10, ""]]
        if isinstance(val, ListRef):
            return [3, [13, val.name, self._list_id(val.name)], [10, ""]]
        if isinstance(val, Arg):
            bid = self._emit_block(Blk("argument_reporter_string_number",
                                       fields={"VALUE": [val.name, None]}), parent_id)
            return [3, bid, [10, ""]]
        if isinstance(val, Blk):
            if val.shadow:
                bid = self._emit_block(val, parent_id)
                return [1, bid]
            bid = self._emit_block(val, parent_id)
            if val.opcode in BOOL_OPCODES:
                return [2, bid]
            return [3, bid, [10, ""]]
        if isinstance(val, list):  # substack
            if not val:
                return None
            first = self._emit_stack(val, parent_id)
            return [2, first]
        raise TypeError(f"valeur non gérée pour {name}: {val!r}")

    def _emit_block(self, blk, parent_id, top=False, x=0, y=0):
        bid = _nid()
        entry = {
            "opcode": blk.opcode, "next": None, "parent": parent_id,
            "inputs": {}, "fields": {}, "shadow": blk.shadow, "topLevel": top,
        }
        if top:
            entry["x"] = x
            entry["y"] = y
        self.blocks[bid] = entry
        for name, val in blk.inputs.items():
            if isinstance(val, ListRef) is False and isinstance(val, list) and len(val) == 0:
                continue
            v = self._emit_value(name, val, bid)
            if v is not None:
                entry["inputs"][name] = v
        for name, val in blk.fields.items():
            if isinstance(val, Var):
                entry["fields"][name] = [val.name, self._var_id(val.name)]
            elif isinstance(val, ListRef):
                entry["fields"][name] = [val.name, self._list_id(val.name)]
            elif isinstance(val, tuple) and val[0] == "broadcast":
                entry["fields"][name] = [val[1], self.project.broadcast_id(val[1])]
            else:
                entry["fields"][name] = val
        if blk.mutation:
            entry["mutation"] = blk.mutation
        return bid

    def _emit_stack(self, blocks, parent_id, top=False, x=0, y=0):
        prev = None
        first = None
        for blk in blocks:
            bid = self._emit_block(blk, parent_id if prev is None else prev, top=(top and prev is None), x=x, y=y)
            if prev is not None:
                self.blocks[prev]["next"] = bid
                self.blocks[bid]["parent"] = prev
            else:
                first = bid
            prev = bid
        return first

    def serialize(self):
        self.blocks = {}
        y = 0
        for sc in self.scripts:
            self._emit_stack(sc, None, top=True, x=0, y=y)
            y += 400
        d = {
            "isStage": self.is_stage, "name": self.name,
            "variables": {vid: [n, v] for n, (vid, v) in self.variables.items()},
            "lists": {lid: [n, v] for n, (lid, v) in self.lists.items()},
            "broadcasts": {},
            "blocks": self.blocks, "comments": {},
            "currentCostume": self.current_costume,
            "costumes": [{k: v for k, v in c.items() if k != "_data"} for c in self.costumes],
            "sounds": [{k: v for k, v in s.items() if k != "_data"} for s in self.sounds],
            "volume": self.volume, "layerOrder": self.layer,
        }
        if self.is_stage:
            d["broadcasts"] = {bid: n for n, bid in self.project.broadcasts.items()}
            d.update({"tempo": 60, "videoTransparency": 50, "videoState": "off", "textToSpeechLanguage": None})
        else:
            d.update({"visible": self.visible, "x": self.x, "y": self.y, "size": self.size,
                      "direction": self.direction, "draggable": self.draggable,
                      "rotationStyle": self.rotation_style})
        return d


class Project:
    def __init__(self):
        self.stage = Target("Stage", is_stage=True)
        self.stage.layer = 0
        self.stage.project = self
        self.sprites = []
        self.broadcasts = {}

    def sprite(self, name):
        t = Target(name)
        t.project = self
        t.layer = len(self.sprites) + 1
        self.sprites.append(t)
        return t

    def broadcast_id(self, name):
        if name not in self.broadcasts:
            self.broadcasts[name] = _nid("m")
        return self.broadcasts[name]

    def build(self, path):
        sprites = [s.serialize() for s in self.sprites]  # d'abord les sprites (remplit la table des messages)
        targets = [self.stage.serialize()] + sprites
        pj = {
            "targets": targets, "monitors": [], "extensions": ["pen"],
            "meta": {"semver": "3.0.0", "vm": "2.3.0", "agent": "ArenaClash-generator"},
        }
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(pj, ensure_ascii=False))
            seen = set()
            for t in [self.stage] + self.sprites:
                for c in t.costumes:
                    if c["md5ext"] not in seen:
                        seen.add(c["md5ext"])
                        z.writestr(c["md5ext"], c["_data"])
                for s in t.sounds:
                    if s["md5ext"] not in seen:
                        seen.add(s["md5ext"])
                        z.writestr(s["md5ext"], s["_data"])
        return pj


# ---------------------------------------------------------------- helpers blocs

def menu(opcode, field, value):
    return Blk(opcode, fields={field: [value, None]}, shadow=True)


# --- événements
def when_flag():
    return Blk("event_whenflagclicked")


def when_broadcast(name):
    return Blk("event_whenbroadcastreceived", fields={"BROADCAST_OPTION": ("broadcast", name)})


def when_clicked():
    return Blk("event_whenthisspriteclicked")


def when_clone_start():
    return Blk("control_start_as_clone")


def when_key(key):
    return Blk("event_whenkeypressed", fields={"KEY_OPTION": [key, None]})


class _Bcast(Blk):
    pass


def broadcast(name):
    b = Blk("event_broadcast")
    b.inputs = {"BROADCAST_INPUT": _BroadcastVal(name)}
    return b


def broadcast_wait(name):
    b = Blk("event_broadcastandwait")
    b.inputs = {"BROADCAST_INPUT": _BroadcastVal(name)}
    return b


class _BroadcastVal(Blk):
    def __init__(self, name):
        super().__init__("__broadcast__")
        self.bname = name


# patch de l'émission pour les broadcasts
_orig_emit_value = Target._emit_value


def _emit_value_patched(self, name, val, parent_id):
    if isinstance(val, _BroadcastVal):
        return [1, [11, val.bname, self.project.broadcast_id(val.bname)]]
    return _orig_emit_value(self, name, val, parent_id)


Target._emit_value = _emit_value_patched


# --- contrôle
def wait(s):
    return Blk("control_wait", {"DURATION": s})


def repeat(n, body):
    return Blk("control_repeat", {"TIMES": n, "SUBSTACK": body})


def forever(body):
    return Blk("control_forever", {"SUBSTACK": body})


def if_(cond, body):
    return Blk("control_if", {"CONDITION": cond, "SUBSTACK": body})


def if_else(cond, body, else_body):
    return Blk("control_if_else", {"CONDITION": cond, "SUBSTACK": body, "SUBSTACK2": else_body})


def repeat_until(cond, body):
    return Blk("control_repeat_until", {"CONDITION": cond, "SUBSTACK": body})


def wait_until(cond):
    return Blk("control_wait_until", {"CONDITION": cond})


def stop(option="this script"):
    hasnext = "true" if option == "other scripts in sprite" else "false"
    return Blk("control_stop", fields={"STOP_OPTION": [option, None]},
               mutation={"tagName": "mutation", "children": [], "hasnext": hasnext})


def create_clone(target="_myself_"):
    return Blk("control_create_clone_of", {"CLONE_OPTION": menu("control_create_clone_of_menu", "CLONE_OPTION", target)})


def delete_clone():
    return Blk("control_delete_this_clone")


# --- données
def set_var(name, val):
    return Blk("data_setvariableto", {"VALUE": val}, {"VARIABLE": Var(name)})


def change_var(name, val):
    return Blk("data_changevariableby", {"VALUE": val}, {"VARIABLE": Var(name)})


def var(name):
    return Var(name)


def list_add(name, item):
    return Blk("data_addtolist", {"ITEM": item}, {"LIST": ListRef(name)})


def list_clear(name):
    return Blk("data_deletealloflist", fields={"LIST": ListRef(name)})


def list_replace(name, idx, item):
    return Blk("data_replaceitemoflist", {"INDEX": idx, "ITEM": item}, {"LIST": ListRef(name)})


def item(name, idx):
    return Blk("data_itemoflist", {"INDEX": idx}, {"LIST": ListRef(name)})


def list_len(name):
    return Blk("data_lengthoflist", fields={"LIST": ListRef(name)})


# --- opérateurs
def add(a, b): return Blk("operator_add", {"NUM1": a, "NUM2": b})
def sub(a, b): return Blk("operator_subtract", {"NUM1": a, "NUM2": b})
def mul(a, b): return Blk("operator_multiply", {"NUM1": a, "NUM2": b})
def div(a, b): return Blk("operator_divide", {"NUM1": a, "NUM2": b})
def mod(a, b): return Blk("operator_mod", {"NUM1": a, "NUM2": b})
def rnd(a): return Blk("operator_round", {"NUM": a})
def lt(a, b): return Blk("operator_lt", {"OPERAND1": a, "OPERAND2": b})
def gt(a, b): return Blk("operator_gt", {"OPERAND1": a, "OPERAND2": b})
def eq(a, b): return Blk("operator_equals", {"OPERAND1": a, "OPERAND2": b})
def and_(a, b): return Blk("operator_and", {"OPERAND1": a, "OPERAND2": b})
def or_(a, b): return Blk("operator_or", {"OPERAND1": a, "OPERAND2": b})
def not_(a): return Blk("operator_not", {"OPERAND": a})
def join(a, b): return Blk("operator_join", {"STRING1": a, "STRING2": b})
def letter(i, s): return Blk("operator_letter_of", {"LETTER": i, "STRING": s})
def strlen(s): return Blk("operator_length", {"STRING": s})
def random(a, b): return Blk("operator_random", {"FROM": a, "TO": b})
def mathop(op, n): return Blk("operator_mathop", {"NUM": n}, {"OPERATOR": [op, None]})
def abs_(n): return mathop("abs", n)
def floor(n): return mathop("floor", n)


def join3(a, b, c): return join(a, join(b, c))
def join4(a, b, c, d): return join(a, join(b, join(c, d)))


def ge(a, b): return not_(lt(a, b))
def le(a, b): return not_(gt(a, b))


# --- mouvement
def goto_xy(x, y): return Blk("motion_gotoxy", {"X": x, "Y": y})
def set_x(x): return Blk("motion_setx", {"X": x})
def set_y(y): return Blk("motion_sety", {"Y": y})
def change_x(x): return Blk("motion_changexby", {"DX": x})
def change_y(y): return Blk("motion_changeyby", {"DY": y})
def point_dir(d): return Blk("motion_pointindirection", {"DIRECTION": d})
def x_pos(): return Blk("motion_xposition")
def y_pos(): return Blk("motion_yposition")
def direction(): return Blk("motion_direction")


def goto_sprite(name):
    return Blk("motion_goto", {"TO": menu("motion_goto_menu", "TO", name)})


def set_rotation_style(style):
    return Blk("motion_setrotationstyle", fields={"STYLE": [style, None]})


# --- apparence
def show(): return Blk("looks_show")
def hide(): return Blk("looks_hide")


def switch_costume(name):
    if isinstance(name, str):
        return Blk("looks_switchcostumeto", {"COSTUME": menu("looks_costume", "COSTUME", name)})
    return Blk("looks_switchcostumeto", {"COSTUME": name})


def switch_backdrop(name):
    if isinstance(name, str):
        return Blk("looks_switchbackdropto", {"BACKDROP": menu("looks_backdrops", "BACKDROP", name)})
    return Blk("looks_switchbackdropto", {"BACKDROP": name})


def set_size(s): return Blk("looks_setsizeto", {"SIZE": s})
def change_size(s): return Blk("looks_changesizeby", {"CHANGE": s})
def size(): return Blk("looks_size")


def set_effect(effect, v):
    return Blk("looks_seteffectto", {"VALUE": v}, {"EFFECT": [effect, None]})


def change_effect(effect, v):
    return Blk("looks_changeeffectby", {"CHANGE": v}, {"EFFECT": [effect, None]})


def clear_effects(): return Blk("looks_cleargraphiceffects")


def go_front(): return Blk("looks_gotofrontback", fields={"FRONT_BACK": ["front", None]})
def go_back(): return Blk("looks_gotofrontback", fields={"FRONT_BACK": ["back", None]})


def go_layers(n, dir_="forward"):
    return Blk("looks_goforwardbackwardlayers", {"NUM": n}, {"FORWARD_BACKWARD": [dir_, None]})


def costume_name(): return Blk("looks_costumenumbername", fields={"NUMBER_NAME": ["name", None]})
def costume_number(): return Blk("looks_costumenumbername", fields={"NUMBER_NAME": ["number", None]})


def say(msg): return Blk("looks_say", {"MESSAGE": msg})
def say_for(msg, secs): return Blk("looks_sayforsecs", {"MESSAGE": msg, "SECS": secs})


# --- capteurs
def key_pressed(key):
    return Blk("sensing_keypressed", {"KEY_OPTION": menu("sensing_keyoptions", "KEY_OPTION", key)})


def touching(obj):
    return Blk("sensing_touchingobject", {"TOUCHINGOBJECTMENU": menu("sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU", obj)})


def mouse_down(): return Blk("sensing_mousedown")
def mouse_x(): return Blk("sensing_mousex")
def mouse_y(): return Blk("sensing_mousey")
def timer(): return Blk("sensing_timer")
def reset_timer(): return Blk("sensing_resettimer")


def of(prop, sprite):
    return Blk("sensing_of", {"OBJECT": menu("sensing_of_object_menu", "OBJECT", sprite)}, {"PROPERTY": [prop, None]})


# --- stylo
def pen_clear(): return Blk("pen_clear")
def pen_stamp(): return Blk("pen_stamp")
def pen_down(): return Blk("pen_penDown")
def pen_up(): return Blk("pen_penUp")
def pen_size(n): return Blk("pen_setPenSizeTo", {"SIZE": n})


def pen_color(hexcol):
    if isinstance(hexcol, str):
        return Blk("pen_setPenColorToColor", {"COLOR": _ColorVal(hexcol)})
    return Blk("pen_setPenColorToColor", {"COLOR": hexcol})


def pen_param(param, v):
    return Blk("pen_setPenColorParamTo", {"COLOR_PARAM": menu("pen_menu_colorParam", "colorParam", param), "VALUE": v})


class _ColorVal(Blk):
    def __init__(self, hexcol):
        super().__init__("__color__")
        self.hexcol = hexcol


_orig_emit_value2 = Target._emit_value


def _emit_value_patched2(self, name, val, parent_id):
    if isinstance(val, _ColorVal):
        return [1, [9, val.hexcol]]
    return _orig_emit_value2(self, name, val, parent_id)


Target._emit_value = _emit_value_patched2


# --- son
def play_sound(name):
    return Blk("sound_play", {"SOUND_MENU": menu("sound_sounds_menu", "SOUND_MENU", name)})


def set_volume(v): return Blk("sound_setvolumeto", {"VOLUME": v})
def stop_sounds(): return Blk("sound_stopallsounds")


# --- blocs personnalisés
def define(proccode, argnames, body, warp=True):
    """proccode ex: 'write %s %n %n'. Retourne la liste [definition, *body]."""
    argids = [_nid("a") for _ in argnames]
    proto_inputs = {}
    for aid, an in zip(argids, argnames):
        proto_inputs[aid] = Blk("argument_reporter_string_number", fields={"VALUE": [an, None]}, shadow=True)
    proto = Blk("procedures_prototype", proto_inputs, shadow=True, mutation={
        "tagName": "mutation", "children": [], "proccode": proccode,
        "argumentids": json.dumps(argids), "argumentnames": json.dumps(argnames),
        "argumentdefaults": json.dumps(["" for _ in argnames]), "warp": "true" if warp else "false",
    })
    defn = Blk("procedures_definition", {"custom_block": proto})
    _PROCS[proccode] = argids
    return [defn] + body


_PROCS = {}


def call(proccode, *args):
    argids = _PROCS[proccode]
    assert len(argids) == len(args), f"mauvais nb d'arguments pour {proccode}"
    inputs = {aid: a for aid, a in zip(argids, args)}
    return Blk("procedures_call", inputs, mutation={
        "tagName": "mutation", "children": [], "proccode": proccode,
        "argumentids": json.dumps(argids), "warp": "true",
    })


def arg(name):
    return Arg(name)
