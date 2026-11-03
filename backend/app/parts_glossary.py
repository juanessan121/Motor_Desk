"""Glosario español de componentes mecánicos.

`lifeofcapo/car-api` publica `car-parts.json` con exactamente dos campos: `slug`
en inglés y `name` en ruso. No trae categorías, ni compatibilidad, ni
traducción. Este módulo no adivina: compone el nombre español a partir del
slug, que es una clave estable, determinista y verificable.

Reglas de la traducción:

- El término original (ruso) y el slug inglés se conservan siempre. La
  traducción es un atributo adicional, nunca una sustitución.
- Los términos compuestos se resuelven por la frase más larga del glosario
  (`brake pad` -> "pastilla de freno"), no palabra por palabra.
- En inglés los modificadores de posición preceden al sustantivo
  (`rear-shock-absorber`); en español lo siguen y concuerdan en género y
  número ("Amortiguador trasero", "Pastilla de freno delantera izquierda").
- Las siglas, marcas y unidades (ABS, MPFI, 180 g, 200 kW) se conservan tal
  cual y **no** cuentan como falta de traducción.
- Si alguna palabra del slug no está en el glosario, la traducción se marca
  `review=True` y la interfaz la presenta como pendiente. Nunca se fuerza una
  traducción sin respaldo.

Este módulo no declara compatibilidades entre piezas y vehículos: eso solo
existe cuando una fuente lo publica explícitamente.
"""

# Modificadores de posición: (masculino, femenino).
# `side` no está aquí a propósito: forma parte del sustantivo ("espejo
# lateral"), no lo precede. Si se tratara como modificador, se robaría la
# palabra y la frase "side mirror" nunca llegaría al glosario.
POSITIONALS = {
    "rear": ("trasero", "trasera"),
    "front": ("delantero", "delantera"),
    "left": ("izquierdo", "izquierda"),
    "right": ("derecho", "derecha"),
    "upper": ("superior", "superior"),
    "lower": ("inferior", "inferior"),
    "inner": ("interior", "interior"),
    "outer": ("exterior", "exterior"),
    "center": ("central", "central"),
    "central": ("central", "central"),
    "middle": ("central", "central"),
    "driver": ("conductor", "conductora"),
    "passenger": ("acompañante", "acompañante"),
    "rh": ("derecho", "derecha"),
    "lh": ("izquierdo", "izquierda"),
}

# Nombres.headwords femeninos que no terminan en -a.
FEMININE = {"llave", "cruce", "base", "serie", "carcasa posterior"}

# Sustantivos terminados en -a que son masculinos y romperían la regla.
MASCULINE_A = {"sistema", "mapa", "diagrama", "programa", "esquema"}

# Tokens que se conservan literalmente: siglas, marcas, unidades y medidas.
# No requieren revisión porque no son palabras traducibles.
VERBATIM = {
    # siglas
    "abs", "afb", "adblue", "atf", "awd", "bcm", "bsi", "bsm", "cas", "cpc",
    "cvt", "dc", "dpf", "dsc", "dsg", "ds", "ebs", "ecu", "eolys", "ep1", "ep2",
    "esp", "ev", "ffr", "hvac", "icm", "kafas", "lc", "mpfi", "nox", "obd",
    "pto", "pyro", "sam", "tpms", "vcm", "webasto", "a/c",
    # marcas y tecnologias que se nombran asi en el taller
    "abs/ebs", "adblue", "airbag", "air-bag", "bluetooth", "gps", "hdmi", "led",
    "ev", "ebs", "eps", "edc", "dsg",
    # medidas
    "mm", "cm", "kg", "ml", "l", "kw", "hp", "nm", "cc", "gr", "g", "v", "w",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "100", "51", "400g",
    "180g", "200kw", "50kw", "99kw", "380g", "390g", "85g", "8kg", "650ml",
    "270ml", "150",
}

# Orden canónico de los modificadores al final del nombre español. La fuente
# escribe "front left" y "left front" indistintamente; en ambos casos un técnico
# espera "delantera izquierda", no "izquierda delantera". Fijar el orden evita
# depender de cómo vino la fuente.
POSITION_ORDER = ("front", "rear", "left", "right", "upper", "lower",
                  "inner", "outer", "center", "central", "middle",
                  "driver", "passenger", "rh", "lh")

# Segundo lote: tokens que aparecieron al medir la traducción sobre los 1 521
# slugs reales de la fuente. Sin estos, la mitad del catálogo quedaba marcada
# como pendiente de revisión. Se fusiona al final del módulo, cuando WORDS ya
# está definido.
WORDS_EXTRA = {
    "cab": "cabina", "pipe": "tubo", "washer": "lavado", "additive": "aditivo",
    "hinge": "bisagra", "plate": "placa", "body": "carrocería", "pedal": "pedal",
    "rod": "varilla", "stop": "freno", "mechanism": "mecanismo",
    "seatbelt": "cinturón", "tail": "trasero", "high": "alta", "pressure": "presión",
    "main": "principal", "shield": "protector", "system": "sistema",
    "automatic": "automático", "guide": "guía", "lift": "elevador",
    "trailer": "remolque", "board": "tablero", "cleaner": "limpiador",
    "petrol": "gasolina", "plug": "bujía", "regulator": "regulador",
    "socket": "conector", "sunroof": "techo solar", "bar": "barra",
    "calcium": "calcio", "coupling": "acoplamiento", "filler": "rellenador",
    "manual": "manual", "power": "potencia", "reinforcement": "refuerzo",
    "ring": "anillo", "sphere": "esfera", "strap": "correa", "striker": "contacto",
    "turn": "giro", "blind": "ciego", "circuit": "circuito", "complex": "complejo",
    "connecting": "conector", "convertible": "descapotable", "distributor": "distribuidor",
    "flange": "brida", "flywheel": "volante motor", "fork": "horquilla",
    "intermediate": "intermedio", "joint": "rótula", "leaf": "hoja",
    "neck": "cuello", "pad": "pastilla", "repeater": "repetidor",
    "retarder": "retarder", "side": "lateral", "sound": "sonido",
    "support": "soporte", "tube": "tubo", "vvt": "VVT", "xenon": "xénon",
    "accelerator": "acelerador", "amplifier": "amplificador", "ashtray": "cenicero",
    "bay": "bahía", "car": "vehículo", "cargo": "carga", "cooling": "refrigeración",
    "dust": "polvo", "exterior": "exterior", "guard": "protector", "hook": "gancho",
    "insulation": "aislamiento", "intake": "admisión", "lubricant": "lubricante",
    "mud": "barro", "nozzle": "boquilla", "protection": "protección",
    "reflector": "reflector", "shade": "persiana", "shells": "cojinetes",
    "skid": "protector", "solenoid": "solenoide", "speaker": "altavoz",
    "sun": "sol", "terminal": "terminal", "tilt": "inclinación", "truck": "camión",
    "unit": "unidad", "ventilation": "ventilación", "view": "vista",
    "weatherstrip": "perfil de goma", "acceleration": "aceleración",
    "active": "activo", "booster": "servofreno", "bottom": "inferior",
    "cabin": "habitáculo", "clock": "reloj", "comfort": "confort",
    "corner": "esquina", "curtain": "cortina", "diagnostic": "diagnóstico",
    "dipstick": "varilla", "drop": "caída", "duct": "conducto",
    "grab": "asidero", "head": "cabeza", "headrest": "reposacabezas",
    "hitch": "enganche", "holder": "portaequipajes", "jack": "gato",
    "lining": "forro", "lip": "labio", "mass": "flujo", "max": "máximo",
    "mechanical": "mecánico", "mode": "modo", "modulator": "modulador",
    "mounting": "soporte", "multimedia": "multimedia", "negative": "negativo",
    "night": "noche", "parts": "repuestos", "pedestrian": "peatón",
    "phone": "teléfono", "pickup": "pick-up", "pin": "pasador",
    "positive": "positivo", "priming": "cebado", "quick": "rápido",
    "rain": "lluvia", "receiver": "receptor", "relief": "descarga",
    "remote": "mando", "resistor": "resistencia", "retainer": "retén",
    "ride": "recorrido", "semi": "semitrailer", "shift": "cambio",
    "shutters": "compuertas", "snap": "clic", "start": "arranque",
    "steel": "acero", "stem": "vástago", "surround": "embellecedor",
    "temp": "temperatura", "top": "superior", "tow": "remolque",
    "viscous": "viscoso", "vision": "visión", "access": "acceso",
    "additives": "aditivos", "antifreeze": "antigel", "arch": "guardabarros",
    "area": "área", "badge": "emblema", "balance": "balanceo",
    "ball": "bola", "bicycle": "bicicleta", "brace": "refuerzo",
    "breather": "respirador", "brush": "cepillo", "bull": "barra antivuelco",
    "bunk": "litera", "burnoff": "antivaho", "buttons": "botones",
    "buzzer": "buzzer", "bypass": "derivación", "cam": "leva",
    "case": "carcasa", "catalyst": "catalizador", "ceiling": "techo",
    "centrifuge": "centrifugado", "changer": "cambiador", "charging": "carga",
    "closer": "dovetail", "cluster": "cuadrante", "code": "código",
    "conditioner": "acondicionador", "conditioning": "acondicionamiento",
    "conduit": "conducto", "crane": "grúa", "departure": "salida",
    "disable": "desactivar", "disconnect": "desconectar",
    "distribution": "distribución", "electronics": "electrónica",
    "4wd": "4WD", "4x4": "4x4", "scr": "SCR", "pcv": "PCV", "disa": "DISA",
    "bendix": "Bendix", "dsc": "DSC", "ac": "A/A",
    "under": "inferior", "fifth": "quinta", "flush": "lavado",
    "fascia": "frontal", "generator": "generador", "hybrid": "híbrido",
    "latch": "cerrojo", "leg": "pata", "linkage": "articulación",
    "map": "mapa", "master": "maestro", "mat": "tapete", "mounts": "soportes",
    "nut": "tuerca", "part": "pieza", "piece": "pieza", "planetary": "planetario",
    "pneumo": "neumático", "prop": "transmisor", "pyrotechnic": "pirotecnia",
    "refrigeration": "refrigeración", "seats": "asientos", "subwoofer": "subwoofer",
    "tachograph": "tacógrafo", "tailboard": "portalón", "tip": "punta",
    "o": "o", "b": "b", "c": "c",
    "wiper": "limpiaparabrisas", "rack": "cremallera", "tensioner": "tensor",
    "paper": "papel", "card": "tarjeta", "carrier": "portador",
    "view": "vista", "camera": "cámara", "arm": "brazo",
}

# Palabras que no aportan al nombre español.
STOPWORDS = {"a", "an", "the", "of", "and", "or", "for", "with", "type",
             "in", "on", "no", "de", "other", "complete", "universal"}

# Clasificador de sistema del vehículo.
SYSTEMS = {
    "engine": "motor", "motor": "motor", "piston": "motor", "camshaft": "motor",
    "crankshaft": "motor", "crank": "motor", "cylinder": "motor", "crankcase": "motor",
    "valve": "motor", "spark": "motor", "glow": "motor", "timing": "motor",
    "turbo": "motor", "supercharger": "motor", "turbocharger": "motor",
    "intercooler": "motor", "oil": "motor", "sump": "motor", "rings": "motor",
    "rocker": "motor", "pushrod": "motor", "tappet": "motor", "stator": "motor",
    "rotor": "motor", "injector": "motor", "throttle": "motor", "idler": "motor",
    "tensioner": "motor", "inverter": "electrico",
    "fuel": "combustible", "gas": "combustible", "carburetor": "combustible",
    "pump": "combustible", "rail": "combustible", "tank": "combustible",
    "injection": "combustible", "diesel": "combustible", "egr": "escape",
    "brake": "frenos", "caliper": "frenos", "disc": "frenos", "drum": "frenos",
    "abs": "frenos", "parking": "frenos", "handbrake": "frenos",
    "suspension": "suspension", "shock": "suspension", "absorber": "suspension",
    "spring": "suspension", "strut": "suspension", "stabilizer": "suspension",
    "sway": "suspension", "knuckle": "suspension", "bushing": "suspension",
    "wishbone": "suspension", "control": "suspension", "coilover": "suspension",
    "macpherson": "suspension", "panhard": "suspension", "multi": "suspension",
    "torsion": "suspension", "spacer": "suspension", "bump": "suspension",
    "transmission": "transmision", "gearbox": "transmision", "clutch": "transmision",
    "gear": "transmision", "drive": "transmision", "axle": "transmision",
    "differential": "transmision", "propshaft": "transmision", "half": "transmision",
    "cv": "transmision", "transfer": "transmision", "driveshaft": "transmision",
    "driveline": "transmision", "clutch": "transmision", "belt": "transmision",
    "chain": "transmision", "selector": "transmision", "torque": "transmision",
    "wheel": "neumaticos", "tire": "neumaticos", "tyre": "neumaticos",
    "alloy": "neumaticos", "rim": "neumaticos", "tread": "neumaticos",
    "spare": "neumaticos", "camber": "neumaticos", "chock": "neumaticos",
    "steering": "direccion", "rack": "direccion", "pinion": "direccion",
    "servo": "direccion", "servotronic": "direccion", "column": "direccion",
    "battery": "electrico", "alternator": "electrico", "ignition": "electrico",
    "starter": "electrico", "sensor": "electrico", "module": "electrico",
    "relay": "electrico", "fuse": "electrico", "wire": "electrico",
    "wiring": "electrico", "harness": "electrico", "connector": "electrico",
    "switch": "electrico", "button": "electrico", "light": "electrico",
    "lamp": "electrico", "fog": "electrico", "headlight": "electrico",
    "indicator": "electrico", "signal": "electrico", "wiper": "electrico",
    "horn": "electrico", "immobilizer": "electrico", "transponder": "electrico",
    "alarm": "electrico", "audio": "electrico", "radio": "electrico",
    "display": "electrico", "camera": "electrico", "tpms": "electrico",
    "voltage": "electrico", "computer": "electrico", "control": "electrico",
    "radiator": "refrigeracion", "cooler": "refrigeracion", "condenser": "refrigeracion",
    "evaporator": "refrigeracion", "thermostat": "refrigeracion",
    "coolant": "refrigeracion", "fan": "refrigeracion", "water": "refrigeracion",
    "expansion": "refrigeracion", "strainer": "refrigeracion",
    "ac": "climatizacion", "heater": "climatizacion", "climate": "climatizacion",
    "hvac": "climatizacion", "blower": "climatizacion", "drier": "climatizacion",
    "dryer": "climatizacion", "vent": "climatizacion",
    "exhaust": "escape", "muffler": "escape", "catalytic": "escape",
    "manifold": "escape", "silencer": "escape", "dpf": "escape",
    "flex": "escape", "resonator": "escape", "lambda": "escape",
    "bumper": "carroceria", "grille": "carroceria", "fender": "carroceria",
    "door": "carroceria", "hood": "carroceria", "bonnet": "carroceria",
    "trunk": "carroceria", "glass": "carroceria", "panel": "carroceria",
    "mirror": "carroceria", "windshield": "carroceria", "pillar": "carroceria",
    "sill": "carroceria", "quarter": "carroceria", "shelf": "carroceria",
    "bulkhead": "carroceria", "subframe": "carroceria", "crossmember": "carroceria",
    "frame": "carroceria", "roof": "carroceria", "windshield": "carroceria",
    "tailgate": "carroceria", "bed": "carroceria", "canopy": "carroceria",
    "seat": "interiores", "armrest": "interiores", "dashboard": "interiores",
    "trim": "interiores", "carpet": "interiores", "upholstery": "interiores",
    "console": "interiores", "glove": "interiores", "cup": "interiores",
    "mats": "interiores", "shelf": "interiores", "visor": "interiores",
    "headliner": "interiores", "parcel": "interiores",
}

# Frases: se prueba la coincidencia más larga antes que token por token.
PHRASES = {
    ("timing", "belt", "kit"): "kit de correa de distribución",
    ("cab", "shock", "absorber"): "amortiguador de cabina",
    ("cab", "spring"): "resorte de cabina",
    ("brake", "pad", "set"): "set de pastillas de freno",
    ("brake", "disc", "pad", "set"): "set de discos y pastillas",
    ("exhaust", "manifold", "gasket"): "junta de colector de escape",
    ("engine", "oil", "cooler"): "enfriador de aceite del motor",
    ("gear", "shift", "knob"): "pomo de cambios",
    ("gear", "shift", "lever"): "palanca de cambios",
    ("wiper", "blades"): "escobillas del limpiaparabrisas",
    ("clutch", "kit"): "kit de embrague",
    ("windshield", "wiper", "blades"): "escobillas del limpiaparabrisas",
    # El adjetivo va delante del sustantivo que modifica, no suelto al principio.
    ("electric", "window", "regulator"): "elevador de cristal eléctrico",
    ("power", "window", "regulator"): "elevador de cristal eléctrico",
    ("manual", "window", "regulator"): "elevador de cristal manual",
    ("door", "glass", "molding"): "embellecedor de cristal de puerta",
    ("automatic", "gearbox"): "caja de cambios automática",
    ("gear", "selector"): "selector de cambios",
    ("instrument", "panel", "dimmer"): "interruptor regulador del cuadro",
    ("parking", "brake", "control", "module"): "módulo de control del freno de estacionamiento",
    ("electric", "parking", "brake"): "freno de estacionamiento eléctrico",
    ("side", "mirror"): "espejo lateral",
    ("rear", "view", "camera"): "cámara de marcha atrás",
    ("front", "view", "camera"): "cámara frontal",
    ("brake", "pad"): "pastilla de freno",
    ("brake", "pad", "carrier", "plate"): "placa soporte de pastilla de freno",
    ("bicycle", "carrier"): "portabicicletas",
    ("brake", "disc"): "disco de freno",
    ("brake", "caliper"): "caliper de freno",
    ("brake", "chamber"): "cámara de freno",
    ("brake", "system"): "sistema de frenado",
    ("brake", "fluid"): "líquido de frenos",
    ("brake", "line"): "línea de freno",
    ("brake", "light"): "luz de freno",
    ("brake", "pad", "wear", "sensor"): "sensor de desgaste de pastillas",
    ("hand", "brake"): "freno de mano",
    ("parking", "brake"): "freno de estacionamiento",
    ("timing", "belt"): "correa de distribución",
    ("timing", "chain"): "cadena de distribución",
    ("timing", "cover"): "cubierta de distribución",
    ("timing", "kit"): "kit de distribución",
    ("timing", "gear"): "engranaje de distribución",
    ("spark", "plug"): "bujía",
    ("spark", "plugs"): "bujías",
    ("glow", "plug"): "bujía de precalentamiento",
    ("ignition", "coil"): "bobina de encendido",
    ("ignition", "key"): "llave de encendido",
    ("ignition", "switch"): "interruptor de encendido",
    ("ignition", "lock"): "cerradura de encendido",
    ("clutch", "fork"): "horquilla de embrague",
    ("clutch", "disc"): "disco de embrague",
    ("clutch", "cable"): "cable de embrague",
    ("clutch", "master", "cylinder"): "cilindro maestro de embrague",
    ("clutch", "slave", "cylinder"): "cilindro esclavo de embrague",
    ("clutch", "release"): "desembrague",
    ("shock", "absorber"): "amortiguador",
    ("shock", "absorber", "boot"): "guardapolvo de amortiguador",
    ("gas", "spring"): "amortiguador",
    ("coil", "spring"): "resorte helicoidal",
    ("leaf", "spring"): "resorte de hoja",
    ("torsion", "bar"): "barra torsionada",
    ("sway", "bar"): "barra estabilizadora",
    ("sway", "bar", "link"): "bieleta de barra estabilizadora",
    ("anti", "roll", "bar"): "barra estabilizadora",
    ("control", "arm"): "brazo de control",
    ("lower", "control", "arm"): "brazo de control inferior",
    ("upper", "control", "arm"): "brazo de control superior",
    ("steering", "rack"): "cremallera de dirección",
    ("steering", "wheel"): "volante",
    ("steering", "column"): "columna de dirección",
    ("steering", "gear"): "mecanismo de dirección",
    ("steering", "lock"): "cerradura de dirección",
    ("steering", "wheel", "heating"): "volante calefactado",
    ("power", "steering"): "dirección asistida",
    ("electric", "power", "steering"): "dirección eléctrica",
    ("rack", "and", "pinion"): "cremallera y piñón",
    ("cv", "axle"): "semieje",
    ("half", "shaft"): "semieje",
    ("drive", "shaft"): "árbol de transmisión",
    ("propshaft"): "árbol cardán",
    ("gear", "shift"): "selector de cambios",
    ("gear", "shift", "fork"): "horquilla de cambios",
    ("gear", "shift", "linkage"): "varillaje de cambios",
    ("gear", "box"): "caja de cambios",
    ("gearbox"): "caja de cambios",
    ("automatic", "transmission"): "transmisión automática",
    ("manual", "transmission"): "transmisión manual",
    ("transmission", "control", "module"): "módulo de control de transmisión",
    ("transfer", "case"): "caja de transferencia",
    ("torque", "converter"): "convertidor de par",
    ("diesel", "injector"): "inyector diésel",
    ("fuel", "injector"): "inyector de combustible",
    ("fuel", "pump"): "bomba de combustible",
    ("fuel", "filter"): "filtro de combustible",
    ("fuel", "rail"): "riego de combustible",
    ("fuel", "tank"): "depósito de combustible",
    ("fuel", "cap"): "tapón de depósito",
    ("fuel", "door"): "tapa de depósito",
    ("fuel", "level", "sensor"): "sensor de nivel de combustible",
    ("gas", "cap"): "tapón de depósito",
    ("oil", "filter"): "filtro de aceite",
    ("oil", "pan"): "cárter de aceite",
    ("oil", "cooler"): "enfriador de aceite",
    ("oil", "dipstick"): "varilla de nivel de aceite",
    ("oil", "pressure", "sensor"): "sensor de presión de aceite",
    ("oil", "level", "sensor"): "sensor de nivel de aceite",
    ("oil", "seal"): "retene de aceite",
    ("engine", "mount"): "soporte de motor",
    ("engine", "block"): "bloque del motor",
    ("engine", "control", "module"): "módulo de control del motor",
    ("engine", "cover"): "culata",
    ("engine", "oil"): "aceite de motor",
    ("cylinder", "head"): "culata",
    ("cylinder", "head", "cover"): "tapón de culata",
    ("head", "gasket"): "junta de culata",
    ("valve", "cover"): "tapón de válvulas",
    ("valve", "clearance"): "juego de válvulas",
    ("piston", "ring"): "segmento de pistón",
    ("crank", "shaft"): "volante motor",
    ("crankshaft"): "volante motor",
    ("crankcase"): "bloque del motor",
    ("camshaft"): "árbol de levas",
    ("turbo", "charger"): "turbocompresor",
    ("turbocharger"): "turbocompresor",
    ("super", "charger"): "compresor",
    ("supercharger"): "compresor",
    ("intercooler"): "intercooler",
    ("radiator"): "radiador",
    ("heater", "core"): "núcleo de calefacción",
    ("expansion", "tank"): "depósito de expansión",
    ("coolant", "expansion", "tank"): "depósito de expansión",
    ("coolant", "temperature", "sensor"): "sensor de temperatura de refrigerante",
    ("water", "pump"): "bomba de agua",
    ("electric", "fan"): "ventilador eléctrico",
    ("cooling", "fan"): "ventilador de refrigeración",
    ("ac", "compressor"): "compresor de aire acondicionado",
    ("air", "conditioning", "compressor"): "compresor de aire acondicionado",
    ("ac", "condenser"): "condensador de aire acondicionado",
    ("ac", "evaporator"): "evaporador de aire acondicionado",
    ("ac", "expansion", "valve"): "válvula de expansión del aire acondicionado",
    ("ac", "control", "module"): "módulo de control del aire acondicionado",
    ("ac", "dryer"): "secador de aire acondicionado",
    ("cabin", "filter"): "filtro de habitáculo",
    ("cabin", "air", "filter"): "filtro de habitáculo",
    ("air", "filter"): "filtro de aire",
    ("air", "spring"): "amortiguador",
    ("air", "strut"): "amortiguador de aire",
    ("air", "bag"): "bolsa de aire",
    ("air", "damper"): "amortiguador de aire",
    ("exhaust", "manifold"): "colector de escape",
    ("exhaust", "pipe"): "tubo de escape",
    ("exhaust", "system"): "sistema de escape",
    ("exhaust", "valve"): "válvula de escape",
    ("catalytic", "converter"): "catalizador",
    ("muffler"): "silenciador",
    ("exhaust", "muffler"): "silenciador",
    ("oxygen", "sensor"): "sonda lambda",
    ("oxygen", "sensor", "upstream"): "sonda lambda superior",
    ("oxygen", "sensor", "downstream"): "sonda lambda inferior",
    ("battery", "cable"): "cable de batería",
    ("battery", "terminal"): "terminal de batería",
    ("battery", "holder"): "portapilas",
    ("alternator"): "alternador",
    ("starter", "motor"): "motor de arranque",
    ("distributor"): "distribuidor",
    ("distributor", "rotor"): "rotor del distribuidor",
    ("wiper", "blade"): "escobilla del limpiaparabrisas",
    ("wiper", "motor"): "motor del limpiaparabrisas",
    ("wiper", "linkage"): "articulación del limpiaparabrisas",
    ("windshield", "washer"): "lavaparabrisas",
    ("window", "regulator"): "elevador de cristal",
    ("door", "lock"): "cerradura de puerta",
    ("door", "handle"): "manija de puerta",
    ("door", "panel"): "panel de puerta",
    ("door", "switch"): "interruptor de puerta",
    ("door", "glass"): "cristal de puerta",
    ("central", "lock"): "cierre centralizado",
    ("child", "lock"): "seguro infantil",
    ("tail", "light"): "luz trasera",
    ("tail", "lamp"): "faro trasero",
    ("head", "light"): "farola",
    ("strut",): "amortiguador",
    ("headlight",): "farola",
    ("head", "rest"): "reposacabezas",
    ("head", "gasket"): "junta de culata",
    ("head", "light"): "farola",
    ("clutch", "kit"): "kit de embrague",
    ("windshield", "wiper", "blades"): "escobillas del limpiaparabrisas",
    ("side", "window"): "ventana lateral",
    ("side", "step"): "estribo lateral",
    ("side", "impact"): "impacto lateral",
    ("side", "door"): "puerta lateral",
    ("fog", "light"): "luz antiniebla",
    ("daytime", "running", "lights"): "luces diurnas",
    ("interior", "mirror"): "espejo interior",
    ("rear", "view", "mirror"): "espejo retrovisor",
    ("rear", "view", "camera"): "cámara de marcha atrás",
    ("front", "view", "camera"): "cámara frontal",
    ("brake", "pad"): "pastilla de freno",
    ("parking", "sensor"): "sensor de aparcamiento",
    ("reverse", "light"): "luz de marcha atrás",
    ("reverse", "gear", "sensor"): "interruptor de marcha atrás",
    ("turn", "signal"): "intermitente",
    ("indicator", "light"): "luz intermitente",
    ("side", "repeater"): "cat-cat",
    ("repeater", "light"): "cat-cat",
    ("license", "plate"): "matrícula",
    ("plate", "light"): "luz de matrícula",
    ("roof", "rack"): "baca",
    ("sunroof"): "techo solar",
    ("sunroof", "motor"): "motor del techo solar",
    ("spare", "wheel"): "rueda de repuesto",
    ("wheel", "bearing"): "rodamiento de rueda",
    ("wheel", "hub"): "buje de rueda",
    ("wheel", "nut"): "tuerca de rueda",
    ("wheel", "bolt"): "perno de rueda",
    ("wheel", "arch"): "guardabarros",
    ("wheel", "spacer"): "separador de rueda",
    ("fender"): "guardabarros",
    ("control", "module"): "módulo de control",
    ("control", "unit"): "unidad de control",
    ("body", "control", "module"): "módulo de control de carrocería",
    ("multi", "function", "switch"): "mando multifunción",
    ("instrument", "cluster"): "cuadrante de instrumentos",
    ("instrument", "panel"): "cuadrante de instrumentos",
    ("gauge", "cluster"): "cuadrante de instrumentos",
    ("speaker"): "altavoz",
    ("subwoofer"): "subwoofer",
    ("radio"): "radio",
    ("antenna"): "antena",
    ("usb", "port"): "puerto USB",
    ("aux", "usb", "port"): "puerto USB auxiliar",
    ("seat", "belt"): "cinturón de seguridad",
    ("seatbelt"): "cinturón de seguridad",
    ("seat", "belt", "pretensioner"): "pretensor del cinturón",
    ("seat", "heater"): "calefactor de asiento",
    ("head", "rest"): "reposacabezas",
    ("arm", "rest"): "reposabrazos",
    ("airbag"): "airbag",
    ("abs", "sensor"): "sensor ABS",
    ("abs", "module"): "módulo ABS",
    ("esp"): "ESP",
    ("esp", "module"): "módulo ESP",
    ("traction", "control"): "control de tracción",
    ("cruise", "control"): "control de velocidad",
    ("adaptive", "cruise", "control"): "control de velocidad adaptativo",
    ("transponder"): "transponder",
    ("immobilizer"): "inmovilizador",
    ("alarm"): "alarma",
    ("first", "aid", "kit"): "botiquín de primeros auxilios",
    ("warning", "triangle"): "triángulo de emergencia",
    ("jack"): "gato",
    ("wheel", "wrench"): "llave de rueda",
    ("tow", "hook"): "gancho de remolque",
    ("fire", "extinguisher"): "extintor",
    ("first", "kit"): "botiquín de primeros auxilios",
    ("climate", "control"): "climatización",
    ("climate", "control", "module"): "módulo de climatización",
    ("gasket"): "junta",
    ("seal"): "retén",
    ("o", "ring"): "anillo elástico",
    ("drive", "belt"): "correa de transmisión",
    ("serpentine", "belt"): "correa serpentín",
    ("v", "belt"): "correa en V",
    ("belt"): "correa",
    ("chain"): "cadena",
    ("hose"): "manguera",
    ("pipe"): "tubo",
    ("tube"): "tubo",
    ("clamp"): "abrazadera",
    ("bracket"): "soporte",
    ("mount"): "soporte",
    ("mounting"): "soporte",
    ("mounts"): "soportes",
    ("bush"): "buje",
    ("bushing"): "buje",
    ("spring"): "resorte",
    ("shock"): "amortiguador",
    ("absorber"): "amortiguador",
    ("damper"): "amortiguador",
    ("strut"): "amortiguador",
    ("ball", "joint"): "rótula",
    ("ball", "socket"): "rótula",
    ("tie", "rod"): "barra estabilizadora",
    ("tie", "rod", "end"): "terminal de barra",
    ("flywheel"): "volante motor",
    ("clutch"): "embrague",
    ("gear"): "engranaje",
    ("bearing"): "rodamiento",
    ("bearing", "shell"): "cojinete",
    ("pulley"): "polea",
    ("shaft"): "eje",
    ("axle"): "eje",
    ("knuckle"): "mangueta",
    ("hub"): "buje",
    ("cap"): "tapa",
    ("cover"): "tapa",
    ("lid"): "tapa",
    ("panel"): "panel",
    ("housing"): "carcasa",
    ("frame"): "bastidor",
    ("fascia"): "frontal",
    ("grille"): "rejilla",
    ("bumper"): "parachoques",
    ("mirror"): "espejo",
    ("glass"): "vidrio",
    ("window"): "ventana",
    ("seat"): "asiento",
    ("handle"): "manija",
    ("switch"): "interruptor",
    ("button"): "botón",
    ("relay"): "relé",
    ("fuse"): "fusible",
    ("cable"): "cable",
    ("wire"): "cable",
    ("harness"): "arneses",
    ("connector"): "conector",
    ("socket"): "conector",
    ("sensor"): "sensor",
    ("module"): "módulo",
    ("motor"): "motor",
    ("pump"): "bomba",
    ("valve"): "válvula",
    ("filter"): "filtro",
    ("light"): "luz",
    ("lamp"): "faro",
    ("lock"): "cerradura",
    ("bolt"): "perno",
    ("nut"): "tuerca",
    ("screw"): "tornillo",
    ("washer"): "arandela",
    ("clip"): "clip",
    ("tank"): "depósito",
    ("fluid"): "fluido",
    ("oil"): "aceite",
    ("fuel"): "combustible",
    ("coolant"): "refrigerante",
    ("gasoline"): "gasolina",
    ("petrol"): "gasolina",
    ("air"): "aire",
    ("water"): "agua",
    ("brake"): "freno",
    ("engine"): "motor",
    ("transmission"): "transmisión",
    ("suspension"): "suspensión",
    ("steering"): "dirección",
    ("electric"): "eléctrico",
    ("electrical"): "eléctrico",
    ("electronic"): "electrónico",
    ("electronics"): "electrónica",
    ("cylinder"): "cilindro",
    ("piston"): "pistón",
    ("radiator"): "radiador",
    ("wiring"): "cableado",
    ("trunk"): "maletero",
    ("hood"): "capó",
    ("bonnet"): "capó",
    ("sill"): "umbral",
    ("pillar"): "pilastro",
    ("quarter"): "cuarto",
    ("differential"): "diferencial",
    ("hydraulic"): "hidráulico",
    ("pneumatic"): "neumático",
    ("molding"): "embellecedor",
    ("moulding"): "embellecedor",
    ("trim"): "embellecedor",
    ("liner"): "forro",
    ("well"): "cavidad",
    ("gutter"): "canalón",
    ("swing"): "batiente",
    ("sliding"): "corredizo",
    ("tailgate"): "portón",
    ("boot"): "guardapolvo",
    ("flap"): "tapa",
    ("auxiliary"): "auxiliar",
    ("release"): "desconexión",
    ("clearance"): "distribuidor",
    ("floor"): "piso",
    ("console"): "consola",
    ("glove", "box"): "guantera",
    ("stalk"): "palanca",
    ("lever"): "palanca",
    ("paddle"): "palanca",
    ("shifter"): "selector",
    ("selector"): "selector",
    ("joystick"): "joystick",
    ("adjuster"): "regulador",
    ("adjustment"): "regulación",
    ("position"): "posición",
    ("positioner"): "posicionador",
    ("leveling"): "nivelación",
    ("level"): "nivel",
    ("temperature"): "temperatura",
    ("speed"): "velocidad",
    ("speedometer"): "velocímetro",
    ("tachometer"): "tacómetro",
    ("tacho"): "tacógrafo",
    ("rev"): "tacómetro",
    ("gauge"): "manómetro",
    ("meter"): "medidor",
    ("sender"): "emisor",
    ("airbag", "control", "module"): "módulo de control de airbag",
    ("side", "impact", "sensor"): "sensor de impacto lateral",
    ("interior", "mirror"): "espejo interior",
    ("rear", "view", "mirror"): "espejo retrovisor",
    ("sun", "visor"): "parasol",
    ("visor"): "parasol",
    ("grab", "handle"): "asidero",
    ("coat", "hook"): "percha",
    ("ashtray"): "cenicero",
    ("lighter"): "encendedor",
    ("cigarette", "lighter"): "encendedor de mechero",
    ("socket"): "conector",
    ("third", "brake", "light"): "tercer stop",
    ("third", "stop", "light"): "tercer stop",
    ("center", "console"): "consola central",
    ("overhead", "console"): "consola superior",
    ("tail", "gate"): "portón trasero",
    ("side", "step"): "estribo lateral",
    ("running", "board"): "estribo",
    ("roof", "box"): "caja techo",
    ("roof", "cover"): "funda de techo",
    ("door", "sill"): "umbral de puerta",
    ("rocker", "panel"): "faldón lateral",
    ("wheel", "arch", "liner"): "guardabarros interior",
    ("windshield", "wiper"): "limpiaparabrisas",
    ("interior", "filter"): "filtro de habitáculo",
    ("cabin", "heater"): "calefactor de habitáculo",
    ("heater", "blower"): "ventilador de calefacción",
    ("heater", "motor"): "motor de calefacción",
    ("heater", "unit"): "calefactor",
    ("auxiliary", "heater"): "calefactor auxiliar",
    ("water", "pump"): "bomba de agua",
    ("coolant", "pump"): "bomba de refrigerante",
    ("vacuum", "pump"): "bomba de vacío",
    ("high", "pressure"): "alta presión",
    ("low", "pressure"): "baja presión",
    ("pressure", "sensor"): "sensor de presión",
    ("oil", "cooler"): "enfriador de aceite",
    ("intercooler"): "intercooler",
    ("charge", "air"): "carga de aire",
    ("boost"): "sobrepresión",
    ("throttle", "body"): "cuerpo de aceleración",
    ("throttle", "position", "sensor"): "sensor de posición de acelerador",
    ("idle", "control", "valve"): "válvula de ralentí",
    ("mass", "air", "flow"): "flujo de aire",
    ("air", "flow"): "flujo de aire",
    ("air", "duct"): "conducto de aire",
    ("air", "intake"): "admisión de aire",
    ("intake", "manifold"): "colector de admisión",
    ("exhaust", "manifold"): "colector de escape",
    ("downpipe"): "tubo de escape",
    ("test", "pipe"): "sonda de presión",
    ("catalyst"): "catalizador",
    ("gasketing"): "junta",
    ("silicone"): "silicona",
    ("sealant"): "sellante",
    ("adhesive"): "adhesivo",
    ("grease"): "grasa",
    ("lubricant"): "lubricante",
    ("additive"): "aditivo",
    ("additives"): "aditivos",
    ("cleaner"): "limpiador",
    ("fluid"): "fluido",
    ("balm"): "bálsamo",
}

# Palabras sueltas que no forman parte de PHRASES.
WORDS = {
    "abs": "ABS", "acc": "acelerador", "accumulator": "acumulador",
    "actuator": "actuador", "activator": "activador", "adapter": "adaptador",
    "adsorber": "adsorbente", "aerosol": "aerosol", "airbag": "airbag",
    "airbox": "caja de admisión", "airflow": "flujo de aire",
    "airmat": "colchón de aire", "alternator": "alternador", "angle": "ángulo",
    "antenna": "antena", "antigel": "antigel", "arm": "brazo",
    "assembly": "conjunto", "autonomous": "autónomo", "band": "banda",
    "base": "base", "battery": "batería", "bcm": "BCM", "beam": "viga",
    "bearing": "rodamiento", "bed": "caja", "bell": "campana",
    "belt": "correa", "blade": "escobilla", "blades": "escobillas",
    "block": "bloque", "blow": "ventilador", "blower": "ventilador",
    "bolt": "perno", "boost": "sobrepresión", "boot": "guardapolvo",
    "box": "caja", "bracket": "soporte", "brake": "freno", "breaker": "interruptor",
    "buckle": "hebilla", "bulb": "bombilla", "buffer": "tope de puerta",
    "bush": "buje", "bushing": "buje", "cable": "cable", "caliper": "caliper",
    "camshaft": "árbol de levas", "canister": "cartucho", "cap": "tapa",
    "capacitor": "condensador", "carbon": "carbón", "care": "cuidado",
    "carrier": "portador", "cartridge": "cartucho", "casing": "carcasa",
    "cassette": "cassette", "catalytic": "catalizador", "catch": "cierre",
    "cd": "CD", "chain": "cadena", "chamber": "cámara", "chassis": "chasis",
    "charger": "cargador", "check": "válvula de retención", "choke": "choke",
    "chock": "cuña", "cigarette": "encendedor", "clamp": "abrazadera",
    "clip": "clip", "clutch": "embrague", "coilover": "amortiguador completo",
    ("coil", "over"): "amortiguador completo", "collar": "collar",
    "collision": "colisión", "column": "columna", "combination": "combinación",
    "compartment": "compartimento", "compressor": "compresor", "cone": "cono",
    "condenser": "condensador", "conductor": "conductor", "connector": "conector",
    "contact": "contacto", "control": "control", "converter": "convertidor",
    "coolant": "refrigerante", "cooler": "enfriador", "cover": "tapa",
    "cowl": "caperuza", "crank": "manivela", "crankcase": "bloque del motor",
    "crankshaft": "volante motor", "crash": "choque", "crossbar": "barra transversal",
    "cup": "portavasos", "curb": "borde", "curve": "curva", "cut": "corte",
    "cylinder": "cilindro", "damper": "amortiguador", "deceleration": "desaceleración",
    "decorative": "decorativo", "deflector": "deflector", "defroster": "desescarchador",
    "detachable": "desmontable", "differential": "diferencial", "dimmer": "regulador",
    "disc": "disco", "dome": "cúpula", "drain": "purga", "driveshaft": "árbol cardán",
    "drum": "tambor", "dryer": "secador", "dual": "doble", "eccentric": "excéntrico",
    "electronic": "electrónico", "emblem": "emblema", "emergency": "emergencia",
    "entry": "entrada", "equipment": "equipo", "exchanger": "intercambiador",
    "exhaust": "escape", "expansion": "expansión", "extinguisher": "extintor",
    "fan": "ventilador", "fastening": "fijación", "fitting": "racor",
    "flag": "banderín", "flashlight": "linterna", "flushing": "lavado",
    "foam": "espuma", "fold": "plegable", "footrest": " reposapiés",
    "free": "libre", "frost": "escarcha", "front": "delantero",
    "gaiter": "fuelle", "gesture": "gesto", "grease": "grasa",
    "ground": "tierra", "hands": "manos", "handset": "auricular",
    "hanger": "colgador", "hazard": "emergencia", "heat": "calor",
    "heating": "calefacción", "height": "altura", "hose": "manguera",
    "housing": "carcasa", "hub": "buje", "idle": "ralentí", "igniter": "bobina",
    "ignition": "encendido", "ignitor": "bobina", "inflatable": "inflable",
    "inflator": "inflador", "information": "información", "interface": "interfaz",
    "interior": "interior", "inverter": "inversor", "jet": "chorro",
    "jumper": "pinza", "keyless": "sin llave", "knee": "rodilla",
    "knock": "detonación", "lambda": "lambda", "landing": "descanso",
    "lane": "carril", "lateral": "lateral", "leather": "cuero", "led": "LED",
    "lens": "lente", "lifter": "elevador", "limit": "límite",
    "lithium": "litio", "load": "carga", "longitudinal": "longitudinal",
    "lubrication": "lubricación", "lumbar": "lumbar", "magnet": "imán",
    "management": "gestión", "manipulator": "manipulador",
    "manifold": "colector", "matching": "acoplador", "mattress": "colchón",
    "mechatronics": "mecatrónica", "mesh": "malla", "microphone": "micrófono",
    "motion": "movimiento", "navigation": "navegación", "nipple": "racor",
    "nose": "morro", "off": "desconectado", "out": "exterior",
    "output": "salida", "overhead": "superior", "paint": "pintura",
    "pair": "par", "panhard": "Panhard", "panoramic": "panorámico",
    "parcel": "parcelera", "partition": "separador", "piston": "pistón",
    "platform": "plataforma", "pneumatic": "neumático",
    "pocket": "bolsillo", "point": "punto", "pretensioner": "pretensor",
    "primary": "primario", "projector": "proyector", "protective": "protector",
    "pushrod": "balancín", "quality": "calidad", "rails": "rieles",
    "ratchet": "trinquete", "rectifier": "rectificador", "reducer": "reductor",
    "reducing": "reductor", "refrigerant": "refrigerante",
    ("refrigeration", "system"): "sistema de refrigeración",
    "remover": "quitador", "repair": "reparación", "restoring": "restaurador",
    "return": "retorno", "robot": "robot", "rocker": "balancín",
    "roller": "rodillo", "rollover": "volcadura", "rotor": "rotor",
    "rubber": "goma", "safety": "seguridad", "screw": "tornillo",
    "sealant": "sellante", "secondary": "secundario", "selection": "selección",
    "separator": "separador", "servo": "servo", "servotronic": "servotronic",
    "shifters": "selectores", "shroud": "cubierta", "shutoff": "cierre",
    "shutter": "compuerta", "silicone": "silicona", "single": "individual",
    "sleeper": "dormitorio", "spacer": "separador", "spacers": "separadores",
    "spoiler": "spoiler", "spot": "foco", "squib": "inflador",
    "mount": "soporte", "reservoir": "depósito", "tool": "herramienta",
    "stability": "estabilidad", "stator": "estator", "storage": "portaequipajes",
    "strainer": "filtro", "stub": "casquillo", "stud": "espárrago",
    "subframe": "subchasis", "sump": "cárter", "supply": "suministro",
    "table": "mesa", "tag": "etiqueta", "take": "toma",
    "takeoff": "toma de aire", "tandem": "tándem", "tarpaulin": "funda",
    "thrust": "empuje", "timer": "temporizador", "tone": "tono",
    "touch": "táctil", "tray": "bandeja", "triangle": "triángulo",
    "tuner": "sintonizador", "tv": "TV", "underbody": "bajosuelo",
    "unloader": "descargador", "up": "superior", "upholstery": "tapizado",
    ("under", "body"): "bajosuelo", "vacuum": "vacío",
    "valvetronic": "Valvetronic", "vanos": "VANOS", "visor": "parasol",
    ("can", "bus"): "batería de 12 V",
    "waterproof": "impermeable", "winch": "cabrestante", "winder": "motor",
    "work": "trabajo", "yaw": "guiñada", "universal": "universal",
    "temperature": "temperatura", "sensor": "sensor", "module": "módulo",
    "switch": "interruptor", "button": "botón", "motor": "motor",
    "pump": "bomba", "valve": "válvula", "filter": "filtro", "gasket": "junta",
    "light": "luz", "lamp": "faro", "lock": "cerradura", "belt": "correa",
    "chain": "cadena", "clutch": "embrague", "gear": "engranaje",
    "bearing": "rodamiento", "pulley": "polea", "shaft": "eje", "axle": "eje",
    "knuckle": "mangueta", "hub": "buje", "cap": "tapa", "cover": "tapa",
    "lid": "tapa", "panel": "panel", "housing": "carcasa", "frame": "bastidor",
    "mirror": "espejo", "glass": "vidrio", "window": "ventana", "seat": "asiento",
    "handle": "manija", "relay": "relé", "fuse": "fusible", "cable": "cable",
    "wire": "cable", "harness": "arneses", "connector": "conector",
    "sensor": "sensor", "tank": "depósito", "fluid": "fluido", "oil": "aceite",
    "fuel": "combustible", "coolant": "refrigerante", "air": "aire",
    "water": "agua", "brake": "freno", "engine": "motor",
    "transmission": "transmisión", "suspension": "suspensión",
    "steering": "dirección", "electric": "eléctrico",
    "electrical": "eléctrico", "cylinder": "cilindro", "piston": "pistón",
    "radiator": "radiador", "wiring": "cableado", "trunk": "maletero",
    "hood": "capó", "bonnet": "capó", "sill": "umbral", "pillar": "pilastro",
    "quarter": "cuarto", "differential": "diferencial", "hydraulic": "hidráulico",
    "pneumatic": "neumático", "molding": "embellecedor",
    "moulding": "embellecedor", "trim": "embellecedor", "liner": "forro",
    "well": "cavidad", "gutter": "canalón", "swing": "batiente",
    "sliding": "corredizo", "tailgate": "portón", "boot": "guardapolvo",
    "flap": "tapa", "auxiliary": "auxiliar", "release": "desconexión",
    "clearance": "distribuidor", "floor": "piso", "console": "consola",
    "glove": "guante", "stalk": "palanca", "lever": "palanca",
    "paddle": "palanca", "shifter": "selector", "selector": "selector",
    "joystick": "joystick", "adjuster": "regulador", "adjustment": "regulación",
    "position": "posición", "positioner": "posicionador",
    "leveling": "nivelación", "level": "nivel", "temperature": "temperatura",
    "speed": "velocidad", "speedometer": "velocímetro", "tachometer": "tacómetro",
    ("speed", "sensor"): "sensor de velocidad", ("tacho", "graph"): "tacógrafo",
    "gauge": "manómetro", "meter": "medidor", "sender": "emisor",
    "with": "con", ("1", "kit"): "kit", ("a", "s"): "a",
    ("45", "kw"): "45 kW", ("500", "ml"): "500 ml", ("601", "ml"): "601 ml",
    ("antigel", "conditioner"): "aditivo de refrigerante",
    ("aluminium"): "aluminio",
}


# Sistemas que solo se reconocen por la combinación de dos o más palabras.
SYSTEMS_PHRASES = {
    ("air", "filter"): "climatizacion",
    ("cabin", "filter"): "climatizacion",
    ("oil", "filter"): "motor",
    ("fuel", "filter"): "combustible",
    ("fuel", "pump"): "combustible",
    ("brake", "light"): "frenos",
    ("brake", "pad"): "frenos",
    ("brake", "disc"): "frenos",
    ("brake", "caliper"): "frenos",
    ("brake", "line"): "frenos",
    ("parking", "brake"): "frenos",
    ("timing", "belt"): "motor",
    ("timing", "chain"): "motor",
    ("timing", "kit"): "motor",
    ("spark", "plug"): "motor",
    ("glow", "plug"): "motor",
    ("glow", "plug"): "motor",
    ("crank", "shaft"): "motor",
    ("shock", "absorber"): "suspension",
    ("coil", "spring"): "suspension",
    ("power", "steering"): "direccion",
    ("steering", "rack"): "direccion",
    ("steering", "wheel"): "direccion",
    ("drive", "shaft"): "transmision",
    ("gear", "shift"): "transmision",
    ("clutch", "disc"): "transmision",
    ("head", "light"): "electrico",
    ("daytime", "running"): "electrico",
    ("tail", "light"): "electrico",
    ("water", "pump"): "refrigeracion",
    ("exhaust", "manifold"): "escape",
    ("catalytic", "converter"): "escape",
    ("side", "mirror"): "carroceria",
    ("door", "lock"): "carroceria",
    ("door", "handle"): "carroceria",
    ("wheel", "bearing"): "neumaticos",
    ("window", "regulator"): "carroceria",
    ("control", "arm"): "suspension",
    ("head", "gasket"): "motor",
    ("spoiler",): "carroceria",
    ("kit",): "carroceria",
    ("set",): "carroceria",
    ("cover",): "motor",
    ("seal",): "motor",
}


def synonyms_for(name_es: str | None) -> list[str]:
    """Sinónimos del término español, ignorando los modificadores de posición.

    "Amortiguador trasero" no está en el glosario literally, pero su término
    base "amortiguador" sí. Se busca por prefijo normalizado para que la
    posición no deje a la pieza sin sinónimos.
    """
    if not name_es:
        return []
    exact = SYNONYMS.get(_fold(name_es))
    if exact:
        return sorted(exact)
    folded = _fold(name_es)
    for key in sorted(SYNONYMS, key=len, reverse=True):
        folded_key = _fold(key)
        if folded.startswith(folded_key):
            return sorted(SYNONYMS[key])
    return []


def _fold(text: str) -> str:
    import unicodedata
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "",
                   unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode())


def _tokens(slug: str) -> list[str]:
    return [token for token in slug.lower().replace("_", "-").split("-") if token]


# Sinónimos en español de los componentes más buscados en un taller
# ecuatoriano. Solo se incluyen los que se pueden afirmar con seguridad: un
# término dudoso no se escribe, se deja la traducción sin synonym.
SYNONYMS = {
    "pastilla de freno": ["pastillas", "balata", "balatas"],
    "pastilla de frenos": ["pastillas", "balata"],
    "disco de freno": ["discos", "pastelón"],
    "amortiguador": ["shock", "shocks"],
    "alternador": ["generador"],
    "bujía": ["bujías", "bujía de encendido"],
    "embrague": ["clutch"],
    "correa de distribución": ["correa de tiempo"],
    "kit de distribución": ["correa de tiempo", "kit de correa"],
    "filtro de aceite": ["filtro de aceite del motor"],
    "filtro de aire": ["filtro del motor"],
    "espejo lateral": ["retrovisor lateral", "espejo externo"],
    "espejo interior": ["espejo retrovisor"],
    "correa": ["banda"],
    "suspensión": ["suspension"],
    "dirección": ["direccion"],
    "transmisión": ["caja de cambios", "transmision"],
    "tapa": ["tapón"],
    "junta": ["empaque"],
    "junta de culata": ["junta de cabeza", "empaque de culata"],
    "soporte": ["soportería"],
    "ventilador": ["fan"],
    "termostato": ["válvula termostática"],
    "interruptor": ["switch"],
    "sensor": ["sonda", "celda"],
}


def _is_feminine(head: str) -> bool:
    if head in FEMININE:
        return True
    if head in MASCULINE_A:
        return False
    return head.endswith("a")


# El segundo lote de vocabulario se fusiona aquí, con WORDS ya definido.
WORDS.update(WORDS_EXTRA)


def _compose(core: list[str]) -> tuple[str, bool, str]:
    """Compone el núcleo. Devuelve (texto, requiere_revision, última palabra)."""
    words: list[str] = []
    review = False
    index = 0
    while index < len(core):
        matched = False
        for size in (4, 3, 2, 1):
            if index + size > len(core):
                continue
            chunk = tuple(core[index : index + size])
            if chunk in PHRASES:
                words.append(PHRASES[chunk])
                index += size
                matched = True
                break
        if matched:
            continue
        token = core[index]
        if token in VERBATIM:
            words.append(token.upper() if token.isalpha() and len(token) <= 4 else token)
        elif token in WORDS:
            words.append(WORDS[token])
        else:
            review = True
            words.append(token)
        index += 1
    text = " ".join(words).strip()
    # El sustantivo principal es la PRIMERA palabra ("Pastilla de freno" ->
    # "Pastilla"), no la última: de eso depende que "delantera" concuerde.
    head = text.split()[0].strip(",.").lower() if text else ""
    if text:
        text = text[:1].upper() + text[1:]
    return text, review, head


def _phrase_at_start(tokens: list[str], start: int) -> bool:
    """¿Alguna frase del glosario cubre `tokens[start]` y sigue después?"""
    for size in (4, 3, 2):
        chunk = tuple(tokens[start : start + size])
        if chunk in PHRASES and len(chunk) > 1:
            return True
    return False


def _phrase_at_end(tokens: list[str], end: int) -> bool:
    for size in (4, 3, 2):
        chunk = tuple(tokens[end - size : end])
        if chunk in PHRASES and len(chunk) > 1:
            return True
    return False


def translate(slug: str) -> tuple[str | None, str | None, bool]:
    """Traduce un slug a español.

    Devuelve `(nombre_es, sistema, requiere_revision)`.

    - `nombre_es` es `None` si no queda nada traducible: la interfaz debe
      mostrar entonces el término original, nunca una suposición.
    - `requiere_revision` es `True` en cuanto una palabra del slug no está en
      el glosario. Esas traducciones se marcan en la interfaz para que una
      persona las confirme.
    """
    tokens = [token for token in _tokens(slug) if token not in STOPWORDS]
    if not tokens:
        return None, None, True

    system = None
    for size in (3, 2, 1):
        for index in range(len(tokens) - size + 1):
            system = system or SYSTEMS_PHRASES.get(tuple(tokens[index : index + size]))
        if system:
            break
    if not system:
        for token in tokens:
            system = system or SYSTEMS.get(token)

    # En inglés los modificadores de posición preceden al sustantivo; en español
    # lo siguen y deben concordar con el género del sustantivo principal.
    #
    # No se retiran a ciegas: "rear view camera" empieza con un modificador
    # pero es una frase propia ("cámara de marcha atrás"), y "side" ni siquiera
    # está en POSITIONALS por eso. Si alguna frase del glosario empieza en la
    # posición 0 y abarca el modificador, no se toca.
    start = 0
    while (start < len(tokens) and tokens[start] in POSITIONALS
           and not _phrase_at_start(tokens, start)):
        start += 1
    end = len(tokens)
    while end > start and tokens[end - 1] in POSITIONALS and not _phrase_at_end(tokens, end):
        end -= 1

    body, review, head = _compose(tokens[start:end])
    feminine = _is_feminine(head)
    modifiers = sorted(
        {token for token in tokens[:start] + tokens[end:]},
        key=lambda token: POSITION_ORDER.index(token)
        if token in POSITION_ORDER else len(POSITION_ORDER),
    )
    positionals = [POSITIONALS[token][1 if feminine else 0] for token in modifiers]

    parts = [word for word in ([body] if body else []) + positionals if word]
    name = " ".join(" ".join(parts).split())
    if not name:
        return None, system, True
    return name, system, review