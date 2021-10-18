"""
Reader module for CASTEP `castep_bin` files, a binary dump
file that can contain the parameters, cell, model, and results
(e.g., energies, forces, densities, wavefunctions) for a partciular
CASTEP run.

Reading this file can be beneficial as it uses the native floating-point
precision of the CASTEP run itself.

This implementation takes inspiration from similar functions in the
the [Euphonic](https://github.com/pace-neutrons/Euphonic) package.

"""

from typing import Union, Dict, Any, Tuple, Collection, Optional
from pathlib import Path
from struct import unpack
import io


__all__ = ("read_castep_bin",)


CASTEP_BIN_HEADERS = {
    "FORCES": {"forces": (">f8", (3, -1))},
    "FORCE_CON": {
        "phonon_supercell_matrix": (">i4", (3, 3)),
        "phonon_force_constant_matrix": (">f8", (3, "n", 3, "n", "m")),
        "phonon_supercell_origins": (">i4", (3, "m")),
        "phonon_force_constant_row": (">i4", (1,)),
    },
}


def read_castep_bin(
    filename: Union[str, Path], records_to_extract: Collection[str]
) -> Dict[str, Any]:
    """
    Read a castep_bin file for a given CASTEP run.

    Fortran binary files consist of records, one for each Fortran `write`
    statement used to create the file. Each record is surrounded by
    a *record marker* that encodes the length of the record in bytes.

    The length of the record markers themselves are compiler-dependent,
    but ifort and gfortran 4.2+ have settled on 4-byte markers with an
    additional sign bit to indicate that more data follows.

    Further notes on this can be found in the documentation of the
    [FortranFiles.jl](https://traktofon.github.io/FortranFiles.jl/stable/files.html#Terminology-1)
    Julia package.

    CASTEP then additionally organises these records into sections
    denoted by string headers (with possible values from `CASTEP_BIN_HEADERS`),
    which themselves are Fortran file records.

    For example, a file might be structured like:

        <length of string header>
        <string header>
        <length of string header>
        <length of binary data in bytes (record marker)>
        <binary data>
        <length of binary data in bytes (record marker)>

    Args:
        filename (str): name of the file to be read

    Returns:
        A dictionary following the CASTEP header hierarchy found within
        the castep_bin file, containing the decoded data.

    """

    header_offset_map = _generate_header_offset_map(filename)

    castep_data = {}

    for header in records_to_extract:
        if header not in header_offset_map:
            raise RuntimeError(f"Unable to read desired header {header} from file.")

        with open(filename, "rb") as f:
            castep_data[header] = _decode_records(f, header, header_offset_map[header])

    return castep_data


def _decode_records(data, header, offset):
    if header not in CASTEP_BIN_HEADERS:
        raise RuntimeError(
            f"Cannot decode data for header {header}, no record specification found."
        )

    import numpy as np

    decoded_data = {}
    record_spec = CASTEP_BIN_HEADERS[header]
    data.seek(offset)
    for subrecord in record_spec:
        dtype, shape = record_spec[subrecord]
        record_data, marker = _read_record(data)
        count = marker // int(dtype[-1])
        decoded_data[subrecord] = np.frombuffer(record_data, np.dtype(dtype), count=count)

    # Now reshape the arrays and try to solve for unknown dims
    # if len(shape) > 1:
    #     decoded_data[subrecord] = np.reshape(decoded_data[subrecord], shape).T

    return decoded_data


def _generate_header_offset_map(filename: Union[str, Path]) -> Dict[str, int]:
    """Scans a castep_bin file for recognisable headers, creating a
    dictionary of their byte-offsets within the file. The stored
    offset corresponds to the start of the record immediately
    following the CASTEP header.

    Args:
        filename: The file to read.

    Returns:
        A dictionary of headers mapped to the offsets of the following
        record.

    """
    header_offset_map: Dict[str, int] = {}
    with open(filename, "rb") as f:

        # Check first header is "CASTEP_BIN"
        header, _ = _read_record(f)
        header = header.decode("utf-8").strip("'")
        if header != "CASTEP_BIN":
            raise RuntimeError(
                f"File {filename} does not start with 'CASTEP_BIN' header."
            )

        data = None
        while data != "END":
            data, _ = _read_record(f, seek_only=True)
            try:
                data = data.decode("utf-8").strip("'").strip()
                # Strip any non-alpha fields
                if data and data[0].isalpha() and data.upper() == data:
                    header_offset_map[data] = f.tell()
            except (AttributeError, UnicodeDecodeError):
                pass

    return header_offset_map


def _read_record(
    f: io.BufferedReader,
    seek_only: bool = False,
    record_marker_size: int = 4,
    read_data_smaller_than=512,
) -> Tuple[Optional[bytes], int]:
    """Reads the preceeding record marker for the next record in the
    file, decodes the record data, then reads the suffix record marker,
    eventually returning the decoded record data.

    Args:
        f: The open binary file stream in the buffer.
        record_marker_size: The compiler-dependent size of the record
            marker used to indicate the data record size.
        seek_only: If `True`, do not read the data, but instead skip
            over it.
        read_data_smaller_than: read any data smaller than this number
            of bytes, taking precedence over `seek_only`.

    Returns:
        The byte data from the record, or None, if `seek_only` and the
        record exceeded the chosen size.

    """
    marker = _read_marker(f)
    data = None
    if marker <= read_data_smaller_than or not seek_only:
        data = f.read(marker)
    else:
        # seek from current stream position (SEEK_CUR), indicated by the 1
        f.seek(marker, 1)

    marker_end = _read_marker(f)
    if marker != marker_end:
        raise RuntimeError(
            f"The start ({marker}) and end ({marker_end}) record markers were inconsistent."
        )

    return data, marker


def _read_marker(f: Union[io.BufferedReader, bytes], record_marker_size: int = 4) -> int:
    """Read the next *n* bytes from the buffer and try to interpret them
    as a Fortran record marker (typically uint4, but can depend on
    compiler).

    Args:
        f: An open file buffer.
        record_marker_size: The number of bytes to read as a record marker.

    Returns:
        The integer record marker.

    """

    if isinstance(f, io.BufferedReader):
        f = f.read(record_marker_size)

    return unpack(">I", f[:record_marker_size])[0]
