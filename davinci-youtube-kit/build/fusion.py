"""Minimal writer for DaVinci Resolve / Fusion ``.setting`` macro files.

A ``.setting`` file is a Lua table. This module builds that table from plain
Python objects so every template in the kit is generated from readable code
instead of being hand-edited.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Value wrappers
# --------------------------------------------------------------------------- #
@dataclass
class Raw:
    """Lua code emitted verbatim (e.g. ``FuID { "Screen" }``)."""

    code: str


@dataclass
class Expr:
    """A Fusion expression attached to an input."""

    code: str


@dataclass
class Conn:
    """Connect an input to another tool's output."""

    tool: str
    output: str = "Output"


def FuID(name: str) -> Raw:
    return Raw('FuID { "%s" }' % name)


def lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def lua_val(v) -> str:
    if isinstance(v, Raw):
        return v.code
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        r = repr(float(v)) if isinstance(v, float) else str(v)
        return r[:-2] if r.endswith(".0") else r
    if isinstance(v, str):
        return lua_str(v)
    if isinstance(v, (tuple, list)):
        return "{ " + ", ".join(lua_val(x) for x in v) + " }"
    raise TypeError(f"Unsupported value {v!r}")


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@dataclass
class Tool:
    name: str
    kind: str
    inputs: dict = field(default_factory=dict)
    controls: dict = field(default_factory=dict)  # UserControls
    pos: tuple = (0, 0)
    modifier: bool = False  # modifiers have no ViewInfo
    extra: str = ""  # raw Lua appended inside the tool table

    def render(self, ind: str) -> str:
        i1, i2, i3 = ind + "\t", ind + "\t\t", ind + "\t\t\t"
        out = [f"{ind}{self.name} = {self.kind} {{"]
        if not self.modifier:
            out.append(f"{i1}CtrlWZoom = false,")
            out.append(f"{i1}NameSet = true,")
        if self.inputs:
            out.append(f"{i1}Inputs = {{")
            for k, v in self.inputs.items():
                key = k if k.isidentifier() else f'["{k}"]'
                if isinstance(v, Expr):
                    out.append(f"{i2}{key} = Input {{")
                    out.append(f"{i3}Expression = {lua_str(v.code)},")
                    out.append(f"{i2}}},")
                elif isinstance(v, Conn):
                    out.append(f"{i2}{key} = Input {{")
                    out.append(f"{i3}SourceOp = {lua_str(v.tool)},")
                    out.append(f"{i3}Source = {lua_str(v.output)},")
                    out.append(f"{i2}}},")
                else:
                    out.append(f"{i2}{key} = Input {{ Value = {lua_val(v)}, }},")
            out.append(f"{i1}}},")
        if self.extra:
            out.append(self.extra)
        if not self.modifier:
            out.append(f"{i1}ViewInfo = OperatorInfo {{ Pos = {{ {self.pos[0]}, {self.pos[1]} }} }},")
        if self.controls:
            out.append(f"{i1}UserControls = ordered() {{")
            for cid, c in self.controls.items():
                out.append(f"{i2}{cid} = {{")
                for ck, cv in c.items():
                    if ck == "_options":
                        for opt in cv:
                            out.append(f"{i3}{{ CCS_AddString = {lua_str(opt)} }},")
                    else:
                        out.append(f"{i3}{ck} = {lua_val(cv)},")
                out.append(f"{i2}}},")
            out.append(f"{i1}}},")
        out.append(f"{ind}}},")
        return "\n".join(out)


def slider(name, default, lo, hi, integer=False, allowed=None):
    c = {
        "LINKS_Name": name,
        "LINKID_DataType": "Number",
        "INPID_InputControl": "SliderControl",
        "INP_Default": default,
        "INP_MinScale": lo,
        "INP_MaxScale": hi,
        "INP_Integer": integer,
        "ICS_ControlPage": "Controls",
    }
    if allowed:
        c["INP_MinAllowed"], c["INP_MaxAllowed"] = allowed
    return c


def checkbox(name, default=0):
    return {
        "LINKS_Name": name,
        "LINKID_DataType": "Number",
        "INPID_InputControl": "CheckboxControl",
        "INP_Default": default,
        "INP_Integer": True,
        "ICS_ControlPage": "Controls",
    }


def combo(name, options, default=0):
    return {
        "_options": options,
        "LINKS_Name": name,
        "LINKID_DataType": "Number",
        "INPID_InputControl": "ComboControl",
        "INP_Default": default,
        "INP_Integer": True,
        "INP_MinAllowed": 0,
        "INP_MaxAllowed": len(options) - 1,
        "CC_LabelPosition": "Horizontal",
        "ICS_ControlPage": "Controls",
    }


@dataclass
class Exposed:
    """An input of an inner tool shown in the Edit page Inspector."""

    tool: str
    source: str
    name: str | None = None
    default: object = None
    group: int | None = None


@dataclass
class Macro:
    name: str
    tools: list
    output: str
    exposed: list = field(default_factory=list)
    main_inputs: list = field(default_factory=list)  # [(tool, input, label)]

    def render(self) -> str:
        L = ["{", "\tTools = ordered() {", f"\t\t{self.name} = MacroOperator {{"]
        L.append("\t\t\tInputs = ordered() {")
        for n, (tool, src, label) in enumerate(self.main_inputs, 1):
            L += [
                f"\t\t\t\tMainInput{n} = InstanceInput {{",
                f"\t\t\t\t\tSourceOp = {lua_str(tool)},",
                f"\t\t\t\t\tSource = {lua_str(src)},",
                f"\t\t\t\t\tName = {lua_str(label)},",
                "\t\t\t\t},",
            ]
        for n, e in enumerate(self.exposed, 1):
            L += [f"\t\t\t\tInput{n} = InstanceInput {{",
                  f"\t\t\t\t\tSourceOp = {lua_str(e.tool)},",
                  f"\t\t\t\t\tSource = {lua_str(e.source)},"]
            if e.name:
                L.append(f"\t\t\t\t\tName = {lua_str(e.name)},")
            if e.group is not None:
                L.append(f"\t\t\t\t\tControlGroup = {e.group},")
            if e.default is not None:
                L.append(f"\t\t\t\t\tDefault = {lua_val(e.default)},")
            L.append("\t\t\t\t},")
        L.append("\t\t\t},")
        L += [
            "\t\t\tOutputs = {",
            "\t\t\t\tMainOutput1 = InstanceOutput {",
            f"\t\t\t\t\tSourceOp = {lua_str(self.output)},",
            '\t\t\t\t\tSource = "Output",',
            "\t\t\t\t},",
            "\t\t\t},",
            "\t\t\tViewInfo = GroupInfo { Pos = { 0, 0 } },",
            "\t\t\tTools = ordered() {",
        ]
        x = 0
        for t in self.tools:
            if not t.modifier and t.pos == (0, 0):
                t.pos = (x, 0)
                x += 110
            L.append(t.render("\t\t\t\t"))
        L += ["\t\t\t},", "\t\t},", "\t},", f'\tActiveTool = "{self.name}"', "}", ""]
        return "\n".join(L)


# --------------------------------------------------------------------------- #
# Animation helpers
# --------------------------------------------------------------------------- #
def anim_curves(name: str, mirror: bool = False) -> list[Tool]:
    """Anim Curves modifier: outputs 0..1 across the edit duration.

    This is the modifier Blackmagic recommends for transitions because it
    automatically follows the transition length chosen on the Edit page.
    """
    inputs = {"Source": FuID("Duration"), "Lookup": Conn(name + "Lookup", "Value")}
    if mirror:
        inputs["Mirror"] = 1
    lut = Tool(
        name + "Lookup",
        "LUTBezier",
        modifier=True,
        extra=(
            "\t\t\t\t\tKeyColorSplines = {\n"
            "\t\t\t\t\t\t[0] = {\n"
            "\t\t\t\t\t\t\t[0] = { 0, RH = { 0.333333333333333, 0.333333333333333 }, Flags = { Linear = true } },\n"
            "\t\t\t\t\t\t\t[1] = { 1, LH = { 0.666666666666667, 0.666666666666667 }, Flags = { Linear = true } }\n"
            "\t\t\t\t\t\t}\n"
            "\t\t\t\t\t},\n"
            "\t\t\t\t\tSplineColor = { Red = 255, Green = 255, Blue = 255 },"
        ),
    )
    return [Tool(name, "LUTLookup", inputs, modifier=True), lut]


# Lua snippets used inside expressions -------------------------------------- #
T = "(time-comp.RenderStart)"  # frames since the clip started
R = "(comp.RenderEnd-time)"  # frames left before the clip ends
LEN = "max(comp.RenderEnd-comp.RenderStart,1)"  # clip length in frames


def clamp01(x: str) -> str:
    return f"min(max({x},0),1)"
