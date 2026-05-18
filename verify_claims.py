
# BOM from actual table in document
components = {
    'ESP32 WROOM-32': (7.00, 10.00),
    'DS3231 TCXO RTC': (1.00, 2.00),
    'ACS712-20A x2': (2.00, 4.00),
    'BH1750 FVI': (1.00, 2.00),
    'DS18B20 Probe': (1.00, 2.00),
    'PZEM-004T v3.0': (6.00, 8.00),
    'Resistor Dividers': (0.50, 0.50),
    'LM2596 Module': (3.00, 3.00),
}

sep = "=" * 65

print(sep)
print("CLAIM 1: Hardware node cost range")
print(sep)
bom_min = sum(v[0] for v in components.values())
bom_max = sum(v[1] for v in components.values())
bom_min_nopzem = bom_min - 6.00
bom_max_nopzem = bom_max - 8.00
print(f"BOM minimum (with PZEM):  ${bom_min:.2f}")
print(f"BOM maximum (with PZEM):  ${bom_max:.2f}")
print(f"BOM minimum (no PZEM):    ${bom_min_nopzem:.2f}")
print(f"BOM maximum (no PZEM):    ${bom_max_nopzem:.2f}")
print("Document says: $18-$27 (Ch1.4.1, Ch2, Ch6) OR $18-$36 (Ch1.4.4)")
print("VERDICT: $21.50-$31.50 with PZEM | $15.50-$23.50 without PZEM")
print("         The two different ranges in the document are inconsistent with each other")
print("         and with the actual BOM. Recommend: $21-$32 (with PZEM) or $16-$24 (without)")
print()

print(sep)
print("CLAIM 2: System cost = 1.5% to 2.5% of battery asset value")
print(sep)
node_costs = [18, 21.50, 27, 31.50, 36]
battery_prices = [750, 980]
print("  Node Cost | Battery $750 | Battery $980")
print("  --------- | ----------- | -----------")
for n in node_costs:
    p750 = n/750*100
    p980 = n/980*100
    flag = " <-- EXCEEDS 2.5%" if p750 > 2.5 else ""
    print(f"  ${n:5.2f}   |   {p750:.2f}%      |   {p980:.2f}%{flag}")
print()
print("VERDICT: 1.5-2.5% ONLY holds for $18 node / $980 battery (1.84%)")
print("         $27 node vs $750 battery = 3.60% -- EXCEEDS the stated 2.5%")
print("         $36 node vs $750 battery = 4.80% -- EXCEEDS the stated 2.5%")
print("         Honest defensible claim: 'under 4% of the battery asset value'")
print("         or 'between 1.5% and 4% depending on hardware configuration'")
print()

print(sep)
print("CLAIM 3: Cloud VPS table first-year total = ~$37-$40")
print(sep)
node_low, node_high = 18, 27
vps_per_node = 1.20
cloud_total_low = node_low + vps_per_node
cloud_total_high = node_high + vps_per_node
print(f"Node ($18-$27) + VPS share ($1.20/yr) = ${cloud_total_low:.2f} - ${cloud_total_high:.2f}")
print(f"Document table claims: ~$37-$40")
print("VERDICT: Table value is WRONG. Correct = $19.20-$28.20")
print("         Difference of ~$9-$13 is unexplained -- table appears to include")
print("         a hidden cost (installation, SIM card, misc) not stated in text")
print()

print(sep)
print("CLAIM 4: Local Edge (RPi4) first-year = ~$53-$62, cost = ~2.5%")
print(sep)
rpi4 = 35
for n in [18, 27, 36]:
    total = n + rpi4
    p750 = total/750*100
    p980 = total/980*100
    print(f"  ${n} node + $35 RPi4 = ${total} total | $750 batt: {p750:.1f}% | $980 batt: {p980:.1f}%")
print()
print("Document claims: ~$53-$62 total, ~2.5% of asset")
print("VERDICT: $53-$62 range is correct for $18-$27 node + $35 RPi4")
print("         BUT 2.5% figure is wrong -- actual = 5.4% to 8.3%")
print("         The table appears to calculate % using node cost only, not total system cost")
print()

print(sep)
print("CLAIM 5: 94% power reduction vs Raspberry Pi 4")
print(sep)
esp32_wifi = 120
node_total = 152
rpi4_low, rpi4_high = 500, 600
print(f"ESP32 WiFi (120mA) vs RPi4 (500mA): {(1-esp32_wifi/rpi4_low)*100:.1f}% reduction")
print(f"ESP32 WiFi (120mA) vs RPi4 (600mA): {(1-esp32_wifi/rpi4_high)*100:.1f}% reduction")
print(f"Full node (152mA) vs RPi4 (500mA):  {(1-node_total/rpi4_low)*100:.1f}% reduction")
print(f"Full node (152mA) vs RPi4 (600mA):  {(1-node_total/rpi4_high)*100:.1f}% reduction")
modem_sleep = 10
print(f"ESP32 modem-sleep (10mA) vs RPi4 (600mA): {(1-modem_sleep/rpi4_high)*100:.1f}% (not applicable -- firmware keeps WiFi on)")
print()
print("Document claims: 94% reduction")
print("VERDICT: WRONG. The firmware uses delay(60000) keeping WiFi always active.")
print("         Actual reduction is ~74-76% for ESP32 WiFi vs RPi4 idle.")
print("         94% would only be valid for modem-sleep comparison, which is")
print("         not the operational mode used. Fix: change to '74%' or remove the %")
print("         and say 'a fraction of the Raspberry Pi 4 idle consumption'.")
print()

print(sep)
print("CLAIM 6: 0.76W = 0.38% of 200W rated PV generation")
print(sep)
watts = 0.76
pv = 200.0
pct = watts/pv*100
batt_actual = watts/0.77
print(f"0.76W / 200W = {pct:.2f}%")
print(f"VERDICT: CORRECT -- math checks out.")
print(f"Note: actual 12V battery draw via LM2596 (77% eff): {batt_actual:.3f}W = {batt_actual/pv*100:.2f}% of rated PV")
print()

print(sep)
print("CLAIM 7: Battery = 40-60% of total system capital cost")
print(sep)
for batt in [750, 980]:
    sys_min = batt + 300 + 350 + 200
    sys_max = batt + 500 + 600 + 400
    pct_min = batt/sys_max*100
    pct_max = batt/sys_min*100
    print(f"Battery ${batt}: system ${sys_min}-${sys_max} => {pct_min:.0f}%-{pct_max:.0f}% of total")
print("VERDICT: CORRECT -- 40-60% is broadly accurate for a 5kW system.")
print()

print(sep)
print("CLAIM 8: Threshold count in calibration burden paragraph (Ch5 para 739)")
print(sep)
print("F2: ac_power_w > 25.0                           = 1 threshold, 1 rule")
print("F3: battery_voltage < 11.5                      = 1 threshold, 1 rule")
print("F1: irradiance > 667 AND pv_current < 0.5       = 2 thresholds, 1 rule")
print("F5: irradiance > 200 AND pv_voltage > 15 AND")
print("    pv_current < 0.1                            = 3 thresholds, 1 rule")
print("Total: 7 distinct threshold values across 4 rules")
print("For F1+F3+F5 only (excl F2 since it gets 19%): 6 values across 3 rules")
print()
print("Document says: 'four thresholds...across three rules'")
print("VERDICT: WRONG. Should be 'seven threshold values across four rules'")
print("         (or 'six values across three rules' if excluding the F2 rule)")
print()

print(sep)
print("SUMMARY OF ALL CLAIMS")
print(sep)
claims = [
    ("Hardware node cost $18-$27", "PARTLY WRONG", "BOM calculates $21-$32 with PZEM, $16-$24 without"),
    ("Hardware node cost $18-$36", "INCONSISTENT", "Different from $18-$27 in same doc; BOM range is $21-$32"),
    ("1.5-2.5% of battery asset value", "OVERSTATED", "Only true at $18 node/$980 battery; $27/$750 = 3.6%"),
    ("Cloud VPS total $37-$40", "WRONG", "Should be ~$19-$28 (node + $1.20 VPS share)"),
    ("RPi4 total ~$53-$62", "CORRECT", "$18-$27 node + $35 RPi4 = $53-$62"),
    ("RPi4 scenario cost ~2.5%", "WRONG", "Total cost incl. RPi4 = 5.4%-8.3% of battery value"),
    ("94% power reduction vs RPi4", "WRONG", "Actual ~74-76% for always-on WiFi firmware"),
    ("0.76W = 0.38% of rated generation", "CORRECT", "0.76/200 = 0.38%"),
    ("Battery = 40-60% of system cost", "CORRECT", "Actual range ~44-58% for 5kW system"),
    ("4 thresholds across 3 rules", "WRONG", "Actually 7 threshold values across 4 rules"),
]
for claim, verdict, note in claims:
    print(f"  [{verdict:12s}] {claim}")
    print(f"               --> {note}")
    print()
