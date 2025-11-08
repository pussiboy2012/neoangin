import requests

DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

def get_company_by_inn(inn: str, token: str):
    """
    Возвращает словарь с данными покупателя по ИНН через DaData.
    Пример возвращаемых полей: name, address, inn, kpp.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {'68e5b8f7ddbfa183485105918c8e28cedefad5c7'}"
    }
    try:
        resp = requests.post(DADATA_URL, headers=headers, json={"query": inn}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("suggestions"):
            d = data["suggestions"][0]["data"]
            return {
                "name": d.get("name", {}).get("full_with_opf") or d.get("name", {}).get("full"),
                "address": d.get("address", {}).get("value"),
                "inn": d.get("inn"),
                "kpp": d.get("kpp"),
                "ogrn": d.get("ogrn"),
                "industry": d.get("type"),
                "management": d.get("management", {})  # может содержать ФИО директора
            }
        return None
    except Exception as e:
        # логирование в будущем
        print("DaData error:", e)
        return None

