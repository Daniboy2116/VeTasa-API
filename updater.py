import requests
import json
from datetime import datetime, timezone, timedelta

def get_caracas_time():
    # UTC-4
    return datetime.now(timezone.utc) - timedelta(hours=4)

def fetch_dolar_api(url, fuente_filter):
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        filtered = [item for item in data if item.get('fuente') in fuente_filter]
        return filtered[-30:] # Last 30 items
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def fetch_binance_p2p(trade_type):
    url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "fiat": "VES",
        "page": 1,
        "rows": 20,
        "tradeType": trade_type,
        "asset": "USDT",
        "countries": [],
        "proMerchantAds": False,
        "shieldMerchantAds": False,
        "filterType": "all",
        "periods": [],
        "additionalKycVerifyFilter": 0,
        "publisherType": None,
        "payTypes": [],
        "classifies": ["mass", "profession", "user"]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        data = res.json()
        prices = []
        if "data" in data:
            for item in data["data"]:
                try:
                    price = float(item["adv"]["price"])
                    prices.append(price)
                except:
                    pass
        return prices
    except Exception as e:
        print(f"Error fetching Binance {trade_type}: {e}")
        return []

def build_exchange_rate(rate_type, date_str, rate_value, buy_rate=None, sell_rate=None):
    obj = {
        "id": 0,
        "date": date_str,
        "rateType": rate_type,
        "rateValue": rate_value
    }
    if buy_rate is not None:
        obj["buyRate"] = buy_rate
    if sell_rate is not None:
        obj["sellRate"] = sell_rate
    return obj

def main():
    all_rates = []
    caracas_time = get_caracas_time()
    current_hour_str = caracas_time.strftime("%Y-%m-%d %H:00")
    
    # 1. BCV USD History
    bcv_usd_data = fetch_dolar_api("https://ve.dolarapi.com/v1/historicos/dolares", ["oficial", "bcv"])
    for item in bcv_usd_data:
        date_formatted = f"{item['fecha'][:10]} 00:00"
        all_rates.append(build_exchange_rate("BCV_USD", date_formatted, item["promedio"]))
        
    # Obtener el valor actual exacto (por si el histórico tiene un leve retraso)
    try:
        current_usd = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=10).json()
        oficial_usd = next((x for x in current_usd if x.get("fuente") in ["oficial", "bcv"]), None)
        if oficial_usd:
            # Reemplazar si ya existe para hoy o agregarlo como el valor más nuevo
            all_rates = [r for r in all_rates if not (r["rateType"] == "BCV_USD" and r["date"][:10] == current_hour_str[:10])]
            all_rates.append(build_exchange_rate("BCV_USD", current_hour_str, oficial_usd["promedio"]))
    except:
        pass

    # 2. BCV EUR History
    bcv_eur_data = fetch_dolar_api("https://ve.dolarapi.com/v1/historicos/euros", ["oficial", "bcv"])
    for item in bcv_eur_data:
        date_formatted = f"{item['fecha'][:10]} 00:00"
        all_rates.append(build_exchange_rate("BCV_EUR", date_formatted, item["promedio"]))
        
    try:
        current_eur = requests.get("https://ve.dolarapi.com/v1/euros", timeout=10).json()
        oficial_eur = next((x for x in current_eur if x.get("fuente") in ["oficial", "bcv"]), None)
        if oficial_eur:
            all_rates = [r for r in all_rates if not (r["rateType"] == "BCV_EUR" and r["date"][:10] == current_hour_str[:10])]
            all_rates.append(build_exchange_rate("BCV_EUR", current_hour_str, oficial_eur["promedio"]))
    except:
        pass
        
    # 3. BINANCE USDT History (Using Paralelo)
    paralelo_usd_data = fetch_dolar_api("https://ve.dolarapi.com/v1/historicos/dolares", ["paralelo"])
    for item in paralelo_usd_data:
        date_formatted = f"{item['fecha'][:10]} 00:00"
        all_rates.append(build_exchange_rate("BINANCE_USDT", date_formatted, item["promedio"]))
        
    # 4. BINANCE USDT Current
    buy_prices = fetch_binance_p2p("BUY")
    sell_prices = fetch_binance_p2p("SELL")
    
    if buy_prices and sell_prices:
        venta_rate = sum(buy_prices) / len(buy_prices)
        compra_rate = sum(sell_prices) / len(sell_prices)
        average = round((venta_rate + compra_rate) / 2.0, 2)
        
        final_compra = round(compra_rate, 2)
        final_venta = round(venta_rate, 2)
        
        all_rates = [r for r in all_rates if not (r["rateType"] == "BINANCE_USDT" and r["date"][:10] == current_hour_str[:10])]
        all_rates.append(build_exchange_rate(
            "BINANCE_USDT", 
            current_hour_str, 
            average, 
            buy_rate=final_compra, 
            sell_rate=final_venta
        ))
        
    # Save to JSON
    with open("tasas.json", "w", encoding="utf-8") as f:
        json.dump(all_rates, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated tasas.json with {len(all_rates)} records.")

if __name__ == "__main__":
    main()
