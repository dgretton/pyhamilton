from string import ascii_uppercase


def num_to_well(num: int, rows: int = 8, cols: int = 12, invert: bool = False):
    if invert:
        return ascii_uppercase[num // cols] + str((num % cols) + 1)
    else:
        return ascii_uppercase[num % rows] + str((num // rows) + 1)


def well_to_num(well: str, rows: int = 8, cols: int = 12, invert: bool = False):
    row, col = split_pos(well)
    tmp = []
    for letter in row:
        tmp.append(ascii_uppercase.find(letter))
    total = sum(tmp)

    if invert:
        return (total * col) + cols - 1
    else:
        return (total + (col - 1)) * rows


def split_pos(s: str) -> "tuple(str, int)":
    row = s.rstrip("0123456789")
    col = int(s[len(row) :])
    return row, col
