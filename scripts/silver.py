from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = ROOT / 'dados' / 'bronze'
SILVER_DIR = ROOT / 'dados' / 'silver'

UF_CODES = {
    '11': 'RO',
    '12': 'AC',
    '13': 'AM',
    '14': 'RR',
    '15': 'PA',
    '16': 'AP',
    '17': 'TO',
    '21': 'MA',
    '22': 'PI',
    '23': 'CE',
    '24': 'RN',
    '25': 'PB',
    '26': 'PE',
    '27': 'AL',
    '28': 'SE',
    '29': 'BA',
    '31': 'MG',
    '32': 'ES',
    '33': 'RJ',
    '35': 'SP',
    '41': 'PR',
    '42': 'SC',
    '43': 'RS',
    '50': 'MS',
    '51': 'MT',
    '52': 'GO',
    '53': 'DF',
}


def round_weight(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    try:
        return str(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation as error:
        raise ValueError(f'Peso amostral inválido: {value!r}') from error


def normalize_age_label(age: str) -> str:
    age = age.strip()
    age = age.replace('Menos de 1 mês', 'menos_de_1_mes')
    age = age.replace('100 anos ou mais', '100_ano_ou_mais')
    age = re.sub(r'^(\d+) (?:mês|meses)$', r'\1_mes', age)
    age = re.sub(r'^(\d+) (?:ano|anos)$', r'\1_ano', age)
    return age


def transform_censo() -> Path:
    source_path = BRONZE_DIR / 'censo_bronze.csv'
    output_path = SILVER_DIR / 'censo_silver.csv'
    censo = pd.read_csv(
        source_path,
        dtype=str,
        keep_default_na=False,
        encoding='utf-8-sig',
        usecols=['Idade', 'Populacao_2022', 'Municipio'],
    )
    age_labels = censo['Idade'].str.strip()
    detailed_ages = age_labels.str.fullmatch(
        r'Menos de 1 mês|\d+ (?:mês|meses|ano|anos)|100 anos ou mais'
    )
    censo = censo.loc[detailed_ages].copy()
    censo = censo.rename(columns={
        'Idade': 'faixa_etaria',
        'Populacao_2022': 'qtd_amostra',
        'Municipio': 'municipio',
    })
    censo['faixa_etaria'] = censo['faixa_etaria'].map(normalize_age_label)
    censo['municipio'] = 'SCS-SP'
    censo['qtd_amostra'] = pd.to_numeric(censo['qtd_amostra'], errors='raise')
    censo = censo[['faixa_etaria', 'qtd_amostra', 'municipio']]
    censo.to_csv(output_path, index=False, encoding='utf-8-sig')
    return output_path


def transform_pns() -> Path:
    source_path = BRONZE_DIR / 'pns_bronze.csv'
    output_path = SILVER_DIR / 'pns_silver.csv'
    pns = pd.read_csv(
        source_path,
        dtype=str,
        keep_default_na=False,
        encoding='utf-8-sig',
        usecols=['V0001', 'UPA_PNS', 'C008', 'Q084', 'V00291'],
    )
    pns = pns.rename(columns={
        'V0001': 'uf',
        'UPA_PNS': 'codigo_upa',
        'C008': 'idade',
        'Q084': 'dor_cronica',
        'V00291': 'peso_amostral_pns',
    })

    pns['dor_cronica'] = pns['dor_cronica'].str.strip()
    pns = pns.loc[pns['dor_cronica'].ne('')].copy()

    unknown_uf = sorted(set(pns['uf'].str.strip()) - UF_CODES.keys())
    if unknown_uf:
        raise ValueError(f'Códigos de UF não reconhecidos: {unknown_uf}')
    pns['uf'] = pns['uf'].str.strip().map(UF_CODES)

    unknown_answers = sorted(set(pns['dor_cronica']) - {'1', '2'})
    if unknown_answers:
        raise ValueError(f'Códigos de dor crônica não reconhecidos: {unknown_answers}')
    pns['dor_cronica'] = pns['dor_cronica'].map({'1': '1', '2': '0'})

    pns['idade'] = pns['idade'].str.strip().str.replace(r'^0+(?=\d)', '', regex=True)
    pns['peso_amostral_pns'] = pns['peso_amostral_pns'].map(round_weight)
    pns = pns[['uf', 'codigo_upa', 'idade', 'dor_cronica', 'peso_amostral_pns']]
    pns.to_csv(output_path, index=False, encoding='utf-8-sig')
    return output_path


def main() -> None:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    censo_path = transform_censo()
    pns_path = transform_pns()
    print(f'Base silver do Censo salva: {censo_path}')
    print(f'Base silver da PNS salva: {pns_path}')


main()