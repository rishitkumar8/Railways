import requests

try:
    response = requests.get('http://localhost:8001/parameters_full', timeout=5)
    data = response.json()
    print('Parameters endpoint working!')
    print(f'Sample parameters: P1={data.get("P1", "N/A")}, P11={data.get("P11", "N/A")}, P31={data.get("P31", "N/A")}')
    print(f'Total parameters: {len(data)}')

    # Check if we have the expected parameter ranges
    p1_p10 = [data.get(f'P{i}', 0) for i in range(1, 11)]
    p11_p20 = [data.get(f'P{i}', 0) for i in range(11, 21)]
    p31_p40 = [data.get(f'P{i}', 0) for i in range(31, 41)]

    print(f'Network health params (P1-P10): {len([p for p in p1_p10 if p != 0])} non-zero')
    print(f'Crowding params (P11-P20): {len([p for p in p11_p20 if p != 0])} non-zero')
    print(f'Speed anomaly params (P31-P40): {len([p for p in p31_p40 if p != 0])} non-zero')

except Exception as e:
    print(f'Error: {e}')
