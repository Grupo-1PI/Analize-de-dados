from __future__ import annotations

import argparse
import io
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'dados' / 'bronze'
CENSO_URL = (
    'https://servicodados.ibge.gov.br/api/v3/agregados/9514/periodos/2022/'
    'variaveis/93?localidades=N6[3548807]&classificacao=287[all]'
)
PNS_URL = (
    'https://ftp.ibge.gov.br/PNS/2019/Microdados/Dados/'
    'PNS_2019_20220525.zip'
)
PNS_COLSPECS = [(0, 2), (2, 9), (9, 18), (116, 119), (967, 968), (1425, 1439)]
PNS_COLUMNS = ['V0001', 'V0024', 'UPA_PNS', 'C008', 'Q084', 'V00291']


def capture_censo(refresh: bool) -> None:
    output_path = RAW_DIR / 'censo_resposta_api.csv'
    if output_path.exists() and not refresh:
        print(f'Reutilizando captura existente: {output_path}')
        return

    response = requests.get(
        CENSO_URL, timeout=120, headers={'User-Agent': 'Mozilla/5.0'}
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise ValueError('A API do Censo retornou uma resposta vazia ou inválida.')

    results = payload[0].get('resultados', [])
    rows = []
    for result in results:
        classifications = result.get('classificacoes', [])
        series = result.get('series', [])
        if not classifications or not series:
            continue
        categories = classifications[0].get('categoria', {})
        locality = series[0].get('localidade', {})
        rows.append({
            'Codigo_idade': next(iter(categories.keys()), ''),
            'Idade': next(iter(categories.values()), ''),
            'Populacao_2022': series[0].get('serie', {}).get('2022', ''),
            'Codigo_municipio': locality.get('id', ''),
            'Municipio': locality.get('nome', ''),
        })

    if not rows:
        raise ValueError('A API do Censo não retornou linhas de população.')
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f'Captura do Censo salva: {output_path}')


def capture_pns(refresh: bool) -> None:
    output_path = RAW_DIR / 'pns_variaveis_extraidas.csv'
    if output_path.exists() and not refresh:
        print(f'Reutilizando captura existente: {output_path}')
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pns_capture_') as temp_dir:
        zip_path = Path(temp_dir) / 'pns_microdados.zip'
        temp_csv_path = RAW_DIR / 'pns_variaveis_extraidas.tmp.csv'
        try:
            with requests.get(
                PNS_URL,
                stream=True,
                timeout=(30, 300),
                headers={'User-Agent': 'Mozilla/5.0'},
            ) as response:
                response.raise_for_status()
                with zip_path.open('wb') as zip_file:
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        if block:
                            zip_file.write(block)

            with zipfile.ZipFile(zip_path) as archive:
                with archive.open('PNS_2019.txt') as pns_binary:
                    pns_text = io.TextIOWrapper(pns_binary, encoding='latin-1')
                    chunks = pd.read_fwf(
                        pns_text,
                        colspecs=PNS_COLSPECS,
                        names=PNS_COLUMNS,
                        chunksize=250_000,
                        dtype=str,
                        keep_default_na=False,
                    )
                    first_chunk = True
                    for chunk in chunks:
                        chunk.to_csv(
                            temp_csv_path,
                            index=False,
                            encoding='utf-8-sig' if first_chunk else 'utf-8',
                            mode='w' if first_chunk else 'a',
                            header=first_chunk,
                        )
                        first_chunk = False
            if not temp_csv_path.exists():
                raise ValueError('O arquivo de microdados da PNS não continha linhas.')
            temp_csv_path.replace(output_path)
        finally:
            if temp_csv_path.exists():
                temp_csv_path.unlink()

    print(f'Captura da PNS salva: {output_path}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Captura os CSVs brutos do Censo 2022 e da PNS 2019.'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Baixa novamente as fontes, mesmo quando os CSVs raw já existem.',
    )
    args = parser.parse_args()
    capture_censo(args.refresh)
    capture_pns(args.refresh)


main()