import re
from string import ascii_uppercase
import rsrc_utils as ru


class Sequence:
    def __init__(
        self,
        name: str,
        labwares: list,
        positions: list,
        ranks: list,
        omit: list = None,
    ) -> None:
        self.name = name
        if len(positions) == 0 or len(positions) != len(labwares):
            return
        self.labware = [
            l for _, l in sorted(zip(ranks[::2], labwares), key=lambda pair: pair[0])
        ]
        self.position = [
            p for _, p in sorted(zip(ranks[1::2], positions), key=lambda pair: pair[0])
        ]
        omit = [] if omit is None else omit
        for x in omit:
            try:
                self.position.remove(x)
            except ValueError:
                print(f"Tried to omit {x}. Position not present in plate.")
        self.current = self.position[0]
        self.last = self.position[-1]
        self.total = len(self.position)
        self.used = []

    def next(self, num: int = 1) -> list:
        idx = self.position.index(self.current)
        return [p for p in self.position[idx : idx + num]]

    def remaining(self) -> list:
        idx = self.position.index(self.current)
        return [p for p in self.position[idx:]]

    def next_column(self, channel_num: int = 8) -> list:
        _, col = ru.split_pos(self.current)
        out = []
        for pos in self.remaining():
            _, p_col = ru.split_pos(pos)
            if p_col == col:
                out.append(pos)
        return out[0:channel_num]

    def use(self, pos: list) -> None:
        for p in pos:
            self.used.append(p)
            self.position.remove(p)
        if self.position == []:
            self.current = None
        else:
            self.current = self.position[0]


class Layout:
    def __init__(self, file_path: str, invert: bool = False) -> None:
        if not file_path.endswith(".lay"):
            raise TypeError("Must be a .lay file.")
        buff = ""
        lines = []
        with open(file_path, "rb") as f:
            for c in f.read():
                try:
                    c = bytes([c]).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                buff += c
                if c in "\n\r\t":
                    lines.append(buff.strip("\x00\x02\03\x04"))
                    buff = ""
        if buff:
            lines.append(buff)

        tmp_seqs = {}
        in_default = True
        for line in lines:
            if line.startswith("DataDef"):
                if line.endswith("ML_STAR,"):
                    in_default = False
                elif line.endswith("default,"):
                    in_default = True
            if in_default:
                continue
            if not line.startswith("Seq."):
                continue
            delimd = line.split(".")
            if not len(delimd) >= 3:
                continue
            seq_id = delimd[1]
            if seq_id not in tmp_seqs:
                tmp_seqs[seq_id] = {
                    "Name": "",
                }
            split = line.split(",")
            if "Name" in split[0]:
                tmp_seqs[seq_id]["Name"] = re.findall('"([^"]*)"', split[1])[0]
            if "Item" in split[0]:
                item_id = delimd[3]
                if item_id not in tmp_seqs[seq_id]:
                    tmp_seqs[seq_id][item_id] = {}
                tmp_seqs[seq_id][item_id][
                    "Labware" if split[0].endswith("ObjId") else "Position"
                ] = re.findall('"([^"]*)"', split[1])[0]
        self.sequences = {}
        for i in tmp_seqs.items():
            labware = []
            position = []
            rank = []
            for e in i[1].items():
                if isinstance(e[1], dict):
                    for y in e[1].items():
                        if y[0] == "Labware":
                            labware.append(y[1])
                        else:
                            position.append(y[1])
                        rank.append(int(e[0]))
            self.sequences[i[1]["Name"]] = Sequence(
                i[1]["Name"], labware, position, rank
            )


class Liquid:
    def __init__(self, name) -> None:
        self.name = name


class Plate:
    def __init__(
        self,
        loc: str,
        lay: Layout,
        vols=None,
        liquid_class=None,
    ) -> None:
        self.loc = loc
        self.sequence: Sequence = lay.sequences[loc]

        self.vol = {}
        if vols is None or isinstance(vols, float):
            for pos in self.sequence.position:
                self.vol[pos] = vols if isinstance(vols, float) else 0.0
        elif isinstance(vols, list):
            if len(vols) == len(self.sequence.position):
                for pos, v in zip(self.sequence.position, vols):
                    self.vol[pos] = v
            else:
                raise ValueError(
                    f"Number of volumes not consistent with number of positions\n"
                    f"    Volumes: {len(vols)}  Positions: {len(self.sequence.position)}"
                )
        elif isinstance(vols, dict):
            vols = [0.0] * len(self.sequence.position)
            for pos, _ in vols.items():
                if pos not in self.sequence.position:
                    raise KeyError(f"{pos} not found in sequence positions.")
                self.vol = vols
        else:
            raise TypeError("Volumes must be either float, list, dict, or None.")

        self.liquid_class = {}
        if liquid_class is None or isinstance(liquid_class, Liquid):
            for pos in self.sequence.position:
                self.liquid_class[pos] = (
                    liquid_class if isinstance(liquid_class, Liquid) else None
                )
        elif isinstance(liquid_class, list):
            if len(liquid_class) == len(self.sequence.position):
                for pos, lc in zip(self.sequence.position, liquid_class):
                    if not isinstance(lc, Liquid):
                        raise TypeError("Liquid class list must be all of type Liquid.")
                    self.liquid_class[pos] = lc
            else:
                raise ValueError(
                    f"Number of volumes not consistent with number of positions\n"
                    f"    Liquid classes: {len(liquid_class)}  Positions: {len(self.sequence.position)}"
                )
        elif isinstance(liquid_class, dict):
            for pos, lc in liquid_class.items():
                if pos not in self.sequence.positions:
                    raise KeyError(f"{pos} not found in plate positions.")
                if not isinstance(lc, Liquid):
                    raise TypeError(
                        "Liquid class dict must be of type 'position': Liquid."
                    )
            self.liquid_class = liquid_class
        else:
            raise TypeError("Liquid class must be either Liquid, list, dict, or None.")

    def seq_positions(self, pos: list) -> str:
        out = []
        for p in pos:
            out.append(f"{self.sequence.labware[self.sequence.position.index(p)]},{p}")
        return ";".join(out)

    # def next(self, num: int = 1) -> str:
    #     out = self.sequence.next(num=num)
    #     return self._seq_positions(out)

    # def next_column(self, channel_num: int = 8) -> str:
    #     out = self.sequence.next_column(channel_num=channel_num)
    #     return self._seq_positions(out)

    # def aspirate(
    #     self,
    #     vol,
    #     c: Channels,
    #     channels: str = None,
    #     count: bool = True,
    #     channel_use: int = 1,
    #     mode: int = 0,
    #     c_LLD: int = 5,
    #     p_LLD: int = 0,
    #     follow: bool = True,
    #     depth: float = 2.0,
    #     height: float = 1.0,
    #     max_lld_dif: float = 1.0,
    #     cycles: int = 0,
    #     mix_pos: float = 0.0,
    #     mix_vol: float = 0.0,
    #     touch: bool = False,
    #     **kwargs,
    # ):
    #     c.aspirate()

    # def aspirate(self, c: Channels, vol):
    #     c.aspirate(vols=vol, liquid_class=self.liquid_class, seq=self.sequence.name)


# l = Layout("C:\Program Files (x86)\HAMILTON\Methods\standardlayout.lay")
# pass
