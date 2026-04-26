/**
 * Resolves all normalization and SoC bounds at require-time.
 *
 * Fail-loud philosophy: if any required config is missing or invalid,
 * the process exits immediately rather than silently producing wrong values.
 *
 * Resolution priority for physical maxima:
 *   1. Explicit MAX_X env var  (user-measured / datasheet)
 *   2. Ohm's Law derivation    (RATED_WATTAGE / NOMINAL_VOLTAGE)
 *   3. process.exit(1)         — cannot normalize → refuse to boot
 */

// ── Chemistry lookup table (cell-level voltages) ──────────────────────────────
// V_min/V_max are derived by: cells = round(nominalV / nominalCellV)
// This ensures thresholds scale correctly for any pack voltage (12/24/48V).
const CHEMISTRY_TABLE = {
    LEAD_ACID:   { nominalCellV: 2.00, minCellV: 1.750, maxCellV: 2.115, bulkCellV: 2.400 },
    AGM:         { nominalCellV: 2.00, minCellV: 1.750, maxCellV: 2.115, bulkCellV: 2.350 },
    LITHIUM:     { nominalCellV: 3.20, minCellV: 2.500, maxCellV: 3.350, bulkCellV: 3.650 },
    LIFEPO4:     { nominalCellV: 3.20, minCellV: 2.500, maxCellV: 3.350, bulkCellV: 3.650 },
    LITHIUM_ION: { nominalCellV: 3.65, minCellV: 3.000, maxCellV: 4.000, bulkCellV: 4.200 },
    NMC:         { nominalCellV: 3.65, minCellV: 3.000, maxCellV: 4.000, bulkCellV: 4.200 },
};

// ── Fail-loud helpers ─────────────────────────────────────────────────────────
const fatal = (msg) => {
    console.error(`FATAL: ${msg}`);
    process.exit(1);
};

const env = (key) => {
    const val = parseFloat(process.env[key]);
    return (Number.isFinite(val) && val > 0) ? val : null;
};

const require_bound = (key, derivedFrom) =>
    fatal(`Cannot resolve ${key}. Either set ${key} in .env or provide ${derivedFrom} for Ohm's Law derivation.`);

// ── Step 1: Battery chemistry (hard requirement) ──────────────────────────────
const CHEMISTRY_KEY = (process.env.BATTERY_CHEMISTRY || '').trim().toUpperCase();
if (!CHEMISTRY_KEY || !CHEMISTRY_TABLE[CHEMISTRY_KEY]) {
    fatal('BATTERY_CHEMISTRY not defined. Must be LITHIUM or LEAD_ACID.');
}
const chem = CHEMISTRY_TABLE[CHEMISTRY_KEY];

// ── Step 2: Pack voltage (hard requirement) ───────────────────────────────────
const NOMINAL_V = env('BATTERY_NOMINAL_VOLTAGE_V');
if (!NOMINAL_V) fatal('BATTERY_NOMINAL_VOLTAGE_V is required.');

// ── Step 3: Cell count + SoC bounds ──────────────────────────────────────────
const cells = Math.round(NOMINAL_V / chem.nominalCellV);
const vMin  = parseFloat((cells * chem.minCellV).toFixed(3));   // 0 % SoC floor
const vMax  = parseFloat((cells * chem.maxCellV).toFixed(3));   // 100 % SoC ceiling (resting full)
const vBulk = parseFloat((cells * chem.bulkCellV).toFixed(3));  // bulk charge ceiling (normalization)

// ── Step 4: Rated specs for Ohm's Law derivations ────────────────────────────
const RATED_PV_W  = env('RATED_PV_WATTAGE_W');
const RATED_INV_W = env('RATED_INVERTER_WATTAGE_W');

// ── Step 5: Resolve each normalization bound ──────────────────────────────────
const pvVoltageMax =
    env('MAX_PV_VOLTAGE_V') ||
    (NOMINAL_V ? NOMINAL_V * 1.15 : null) ||
    require_bound('MAX_PV_VOLTAGE_V', 'BATTERY_NOMINAL_VOLTAGE_V');

const pvCurrentMax =
    env('MAX_PV_CURRENT_A') ||
    (RATED_PV_W && NOMINAL_V ? RATED_PV_W / NOMINAL_V : null) ||
    require_bound('MAX_PV_CURRENT_A', 'RATED_PV_WATTAGE_W + BATTERY_NOMINAL_VOLTAGE_V');

const pvPowerMax =
    env('MAX_PV_POWER_W') ||
    RATED_PV_W ||
    require_bound('MAX_PV_POWER_W', 'RATED_PV_WATTAGE_W');

const battCurrentMax =
    env('MAX_BATTERY_CURRENT_A') ||
    (RATED_PV_W && NOMINAL_V ? RATED_PV_W / NOMINAL_V : null) ||
    require_bound('MAX_BATTERY_CURRENT_A', 'RATED_PV_WATTAGE_W + BATTERY_NOMINAL_VOLTAGE_V');

const acPowerMax =
    env('MAX_AC_POWER_W') ||
    RATED_INV_W ||
    require_bound('MAX_AC_POWER_W', 'RATED_INVERTER_WATTAGE_W');

const acVoltageMax =
    env('MAX_AC_VOLTAGE_V') ||
    require_bound('MAX_AC_VOLTAGE_V', 'MAX_AC_VOLTAGE_V');

const acCurrentMax =
    env('MAX_AC_CURRENT_A') ||
    (acPowerMax && acVoltageMax ? acPowerMax / acVoltageMax : null) ||
    require_bound('MAX_AC_CURRENT_A', 'MAX_AC_POWER_W + MAX_AC_VOLTAGE_V');

const irradianceMax =
    env('MAX_IRRADIANCE_WM2') ||
    require_bound('MAX_IRRADIANCE_WM2', 'MAX_IRRADIANCE_WM2');

// ── Export as frozen object ───────────────────────────────────────────────────
const BOUNDS = Object.freeze({
    nominalVoltage: NOMINAL_V,

    socBounds: Object.freeze({
        vMin,
        vMax,
        vBulk,
        deepDischargeV: vMin,   // explicit alias used for deterministic alarm
        cellCount:      cells,
        chemistry:      CHEMISTRY_KEY,
    }),

    pvVoltage:   { max: pvVoltageMax },
    pvCurrent:   { max: pvCurrentMax },
    pvPower:     { max: pvPowerMax },
    battVoltage: { max: vBulk },         // chemistry-derived bulk ceiling, not generic × 1.15
    battCurrent: { max: battCurrentMax },
    battPower:   { max: pvPowerMax },
    acPower:     { max: acPowerMax },
    acCurrent:   { max: acCurrentMax },
    irradiance:  { max: irradianceMax },
});

console.log(
    `[SystemBounds] ${CHEMISTRY_KEY} / ${NOMINAL_V}V / ${cells} cells — ` +
    `SoC: ${vMin}V–${vMax}V | Bulk: ${vBulk}V | PV: ${pvPowerMax}W | AC: ${acPowerMax}W`
);

module.exports = { BOUNDS };
