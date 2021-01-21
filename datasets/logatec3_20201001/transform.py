import glob
import pandas as pd
from os import path, makedirs
from typing import List
from joblib import delayed, Parallel
from datetime import datetime as dt

from collections import OrderedDict

import argparse

TRACE_PATH = path.dirname(path.abspath(__file__))
DATA_PATH = path.join(TRACE_PATH, "data")


TRACE_FILES = path.join(DATA_PATH, "**", "*.txt")

PROJECT_ROOT = path.dirname(path.dirname(TRACE_PATH))
TRANSFORM_OUTPUT_PATH = path.join(PROJECT_ROOT, "output", "dataset-logatec3-20201001")


# TODO: Maybe convert this to state machine? More reliant on regex?


def trx_parser(line: str, device_addr):
    """This is a packet parser."""

    try:
        #print(line)
        start, end = line.find('[') + 1, line.find(']:')
        lgtc_ts = dt.strptime(line[start:end], '%H:%M:%S.%f')

        line = line[end:]
        #print(line)
        start, end = line.find(']:') + 2, line.find('[')
        #print(start, end)
        packet_type = line[start:end].strip()
        #print(packet_type)
        packet_type, counter = packet_type[0], int(packet_type[1:])

    except (ValueError, IndexError) as e:
        return None

    if packet_type not in ['T', 'R']:
        return None

    line = line[end:]
    start, end = line.find('[') + 1, line.find(']')
    vsn_ts = float(line[start:end].replace(':', '.').replace(' ', ''))
    vsn_ts = dt.fromtimestamp(vsn_ts)

    line = line[end:]
    start, end = line.find(']') + 1, line.find('(')
    target = line[start:end].strip()

    target_type = target[0]
    addr = target[1:]
    if addr:
        addr = addr.strip().replace(' ', '0')
    else:
        addr = '0x0000'

    line = line[end:]
    start, end = line.find('('), line.find(')') + 1
    meta = line[start:end]

    channel  = int( meta[ meta.find('C')+1 : meta.find('L') ] )
    length   = int( meta[ meta.find('L')+1 : meta.find('S') ] )
    seq_num  = int( meta[ meta.find('S')+1 : meta.find('|') ] )
    pwr    = float( meta[ meta.find('P')+1 : meta.find(')') ] ) if packet_type == 'T' else None
    rssi     = int( meta[ meta.find('R')+1 : meta.find('Q') ] ) if packet_type == 'R' else None
    lqi      = int( meta[ meta.find('Q')+1 : meta.find(')') ] ) if packet_type == 'R' else None


    src_addr = None
    dst_addr = None

    if packet_type == 'T':
        src_addr = device_addr
        dst_addr = addr

    if packet_type == 'R':
        src_addr = addr
        dst_addr = device_addr

    return dict(
        # Global timestamp (from LGTC3 host device)
        lgtc_ts=lgtc_ts,

        packet_type=packet_type,

        # Internal packet counter (might jump to 0 on rollover or device reset/hang)
        counter=counter,

        # Embedded device's timestamp (counts from 0, possible overflow)
        vsn_ts=vsn_ts,

        # U == unicast, B == broadcast
        target_type=target_type,

        # Addresses
        src_addr=src_addr,
        dst_addr=dst_addr,

        channel=channel,
        packet_length=length,
        seq_num=seq_num,
        pwr=pwr,
        rssi=rssi,
        lqi=lqi,
    )


def ensure_dir(file_path: str) -> str:
    """Function will ensure that directories to file exists. Input is forwarded to output."""
    directory = path.dirname(file_path)
    if not path.exists(directory):
        makedirs(directory)

    return file_path


def get_filenames() -> List[str]:
    """Returns iterator, which iterates through file paths of all Rutgers link traces."""
    filenames = glob.glob(TRACE_FILES, recursive=True)
    assert len(filenames) != 0
    return filenames


def obtain_current_device_addr(fp):
    import re
    for line in fp:
        if 'Node ID' in line:
            node_id = re.findall(r'\d+', line)[-1]
            node_id = int(node_id)
            node_id = hex(node_id).upper().replace('X', 'x')
            return node_id




def parser(filepath: str) -> pd.DataFrame:
    with open(filepath, mode='r') as fp:
        # Find the missing devices ID
        node_id = obtain_current_device_addr(fp)

        data = []

        for line in fp:
            try:
                line = trx_parser(line, node_id)
            except (ValueError) as err:
                line = None

            if line is None:
                #print('Line si None')
                continue

            data.append(line)

        # Leave it to Pandas for conversion to DataFrame
        data = pd.DataFrame.from_dict(data)

        return data


def get_traces(n_jobs=None) -> List[pd.DataFrame]:
    filenames = get_filenames()

    output = Parallel(n_jobs=n_jobs)(delayed(parser)(filename) for filename in filenames)
    assert len(output) != 0
    return output


def save_as_csv(trace: pd.DataFrame) -> None:
    tracename = trace[trace.packet_type == 'T'].iloc[0]['src_addr']


    filename = f"trace_{tracename}.csv"
    output_path = path.join(TRANSFORM_OUTPUT_PATH, filename)

    trace.to_csv(
        ensure_dir(output_path),
        index=False,
        #columns=columns,
    )


def save_as_hdf5(trace: pd.DataFrame) -> None:
    filename = "logatec3-20201001.h5"
    output_path = path.join(TRANSFORM_OUTPUT_PATH, filename)

    tracename = trace[trace.packet_type == 'T'].iloc[0]['src_addr']

    dataset_name = f"trace_{tracename}".replace("-", "_")
    print(dataset_name)
    trace.to_hdf(
        ensure_dir(output_path),
        key=dataset_name,
        # format='table',
        # data_columns=True,
    )


if __name__ == "__main__":
    SUPPORTED_FORMATS = ["hdf5", "h5", "csv"]

    _parser = argparse.ArgumentParser(description="Log-a-Tec 3.0 @ 2020-10-01 transformation")
    _parser.add_argument(
        "-f",
        "--format",
        metavar="FORMAT",
        type=str.lower,
        dest="output_format",
        required=True,
        choices=SUPPORTED_FORMATS,
        help="Select output format (options: h{df}5|csv)",
    )

    _parser.add_argument(
        "-j",
        "--jobs",
        metavar="JOBS",
        type=int,
        dest="n_jobs",
        required=False,
        default=1,
        help="Number of parallel jobs (default: 1)",
    )

    args = _parser.parse_args()

    n_jobs = args.n_jobs

    traces = get_traces(n_jobs=n_jobs)


    if args.output_format in ["h5", "hdf5"]:
        writer = save_as_hdf5

        # HDF5Store does not support parallel R/W nor locking
        n_jobs = 1

    elif args.output_format in ["csv"]:
        writer = save_as_csv

    else:
        raise ValueError(f'Invalid output format: "{args.output_format}"')

    # Do it!
    Parallel(n_jobs=n_jobs)(delayed(writer)(trace) for trace in traces)
