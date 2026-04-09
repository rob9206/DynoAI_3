"""Extract actual VE and AFR tables from a PVV export and write clean CSVs + JSON."""
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

def inhg_to_kpa(inhg: float) -> float:
    return round(inhg * 3.38639, 1)

def parse_pvv_tables(pvv_path):
    tree = ET.parse(pvv_path)
    root = tree.getroot()

    source = ""
    for comment in pvv_path:
        pass
    with open(pvv_path, 'r') as f:
        first_lines = f.read(500)
        if 'Source File Name' in first_lines:
            start = first_lines.index('"', first_lines.index('Source File Name')) + 1
            end = first_lines.index('"', start)
            source = first_lines[start:end]

    tables = {}
    scalars = {}

    for item in root.findall('Item'):
        name = item.get('name', '')
        units = item.get('units', '')
        cols_el = item.find('Columns')
        rows_el = item.find('Rows')

        if cols_el is None or rows_el is None:
            continue

        col_units = cols_el.get('units', '')
        row_units = rows_el.get('units', '')

        cols = [c.get('label') for c in cols_el.findall('Col')]
        col_vals = [float(c) for c in cols]

        rows_data = []
        row_labels = []
        for row in rows_el.findall('Row'):
            label = row.get('label')
            row_labels.append(float(label))
            cells = [float(c.get('value', '0')) for c in row.findall('Cell')]
            rows_data.append(cells)

        if len(col_vals) == 1 and len(row_labels) == 1:
            scalars[name] = rows_data[0][0]
        else:
            tables[name] = {
                'name': name,
                'units': units,
                'col_units': col_units,
                'row_units': row_units,
                'cols': col_vals,
                'rows': row_labels,
                'values': rows_data,
            }

    return tables, scalars, source


def deduplicate_rows(table):
    """Remove duplicate RPM rows (PVV pads with repeated 8000 RPM rows)."""
    seen = set()
    new_rows = []
    new_vals = []
    for i, rpm in enumerate(table['rows']):
        if rpm not in seen:
            seen.add(rpm)
            new_rows.append(rpm)
            new_vals.append(table['values'][i])
    table['rows'] = new_rows
    table['values'] = new_vals
    return table


def write_ve_csv(filepath, table, title, convert_to_kpa=False):
    cols = table['cols']
    if convert_to_kpa:
        cols = [inhg_to_kpa(c) for c in cols]
        col_header = 'MAP (kPa)'
    else:
        col_header = f'MAP ({table["col_units"]})'

    row_labels = table['rows']
    if 'rpmx1000' in table['row_units'].lower() or 'rpm x 1000' in table['row_units'].lower():
        row_labels = [r * 1000 for r in row_labels]

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([title])
        writer.writerow([f'RPM \\ {col_header}'] + [str(c) for c in cols])
        for i, rpm in enumerate(row_labels):
            writer.writerow([str(int(rpm))] + [str(v) for v in table['values'][i]])


def print_ve_table(title, table, convert_to_kpa=False):
    cols = table['cols']
    if convert_to_kpa:
        cols = [inhg_to_kpa(c) for c in cols]
        unit = 'kPa'
    else:
        unit = table['col_units']

    row_labels = table['rows']
    if 'rpmx1000' in table['row_units'].lower():
        row_labels = [r * 1000 for r in row_labels]

    print(f"\n{'=' * 120}")
    print(f"  {title}")
    print(f"{'=' * 120}")

    header = f"{'RPM':>6} |"
    for c in cols:
        header += f" {c:>6}"
    print(header)
    print("-" * len(header))

    for i, rpm in enumerate(row_labels):
        row = f"{int(rpm):>6} |"
        for v in table['values'][i]:
            row += f" {v:>6}"
        print(row)


def main():
    pvv_path = sys.argv[1] if len(sys.argv) > 1 else r'c:\Users\dawso\Downloads\valueseport.pvv'
    tables, scalars, source = parse_pvv_tables(pvv_path)

    displacement = scalars.get('Engine Displacement', 'unknown')
    cal_id_vals = tables.get('Calibration ID', {}).get('values', [[]])[0]
    cal_id = ''.join(chr(int(v)) for v in cal_id_vals if 32 <= v < 127)

    print(f"Source: {source}")
    print(f"Engine: {displacement} CID")
    print(f"Calibration ID: {cal_id}")
    print(f"Total tables: {len(tables)}, Scalars: {len(scalars)}")

    ve_front = tables.get('VE (MAP based/Front Cyl)')
    ve_rear = tables.get('VE (MAP based/Rear Cyl)')
    afr = tables.get('Air-Fuel Ratio')

    if ve_front:
        ve_front = deduplicate_rows(ve_front)
        print_ve_table(
            f"FRONT CYLINDER VE TABLE (%) -- {displacement} CID -- Cal: {cal_id}",
            ve_front, convert_to_kpa=True
        )

    if ve_rear:
        ve_rear = deduplicate_rows(ve_rear)
        print_ve_table(
            f"REAR CYLINDER VE TABLE (%) -- {displacement} CID -- Cal: {cal_id}",
            ve_rear, convert_to_kpa=True
        )

    if afr:
        afr = deduplicate_rows(afr)
        print_ve_table(
            f"AFR TARGET TABLE -- {displacement} CID -- Cal: {cal_id}",
            afr, convert_to_kpa=True
        )

    # Write output files
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', 'fxdls_baseline')
    os.makedirs(output_dir, exist_ok=True)

    def rpm_labels(t):
        if 'rpmx1000' in t['row_units'].lower():
            return [r * 1000 for r in t['rows']]
        return t['rows']

    if ve_front:
        write_ve_csv(
            os.path.join(output_dir, 'VE_Front_Baseline_FXDLS.csv'),
            ve_front,
            f'Front Cylinder VE (%) - {displacement} CID TC110 FXDLS - Cal: {cal_id}',
            convert_to_kpa=True,
        )

    if ve_rear:
        write_ve_csv(
            os.path.join(output_dir, 'VE_Rear_Baseline_FXDLS.csv'),
            ve_rear,
            f'Rear Cylinder VE (%) - {displacement} CID TC110 FXDLS - Cal: {cal_id}',
            convert_to_kpa=True,
        )

    if afr:
        write_ve_csv(
            os.path.join(output_dir, 'AFR_Targets_FXDLS.csv'),
            afr,
            f'AFR Targets - {displacement} CID TC110 FXDLS - Cal: {cal_id}',
            convert_to_kpa=True,
        )

    # JSON for DynoAI import
    map_bins_kpa = [inhg_to_kpa(c) for c in ve_front['cols']] if ve_front else []
    rpm_bins = [int(r) for r in rpm_labels(ve_front)] if ve_front else []

    summary = {
        'bike': {
            'year': 2017,
            'model': 'FXDLS Low Rider S',
            'engine': f'Twin Cam {int(displacement)} (Screamin Eagle)',
            'displacement_ci': int(displacement),
            'displacement_cc': int(float(displacement) * 16.387),
            'calibration_id': cal_id,
        },
        'mods': ['High-flow air cleaner', 'Bassani 2-1 Road Rage exhaust'],
        'source_pvv': source,
        'grid': {
            'rpm_bins': rpm_bins,
            'map_bins_inhg': ve_front['cols'] if ve_front else [],
            'map_bins_kpa': map_bins_kpa,
        },
        've_front': ve_front['values'] if ve_front else [],
        've_rear': ve_rear['values'] if ve_rear else [],
        'afr_targets': afr['values'] if afr else [],
        'afr_map_bins_kpa': [inhg_to_kpa(c) for c in afr['cols']] if afr else [],
        'afr_rpm_bins': [int(r) for r in rpm_labels(afr)] if afr else [],
    }

    with open(os.path.join(output_dir, 'baseline_config.json'), 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nFiles written to: {os.path.abspath(output_dir)}")
    print(f"  - VE_Front_Baseline_FXDLS.csv")
    print(f"  - VE_Rear_Baseline_FXDLS.csv")
    print(f"  - AFR_Targets_FXDLS.csv")
    print(f"  - baseline_config.json")


if __name__ == '__main__':
    main()
