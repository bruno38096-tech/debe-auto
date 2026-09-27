"""Vehicle selector catalog and query normalization for DEBE Search beta.

The UI uses plain-language body styles; query aliases translate them into the
manufacturer terminology commonly used by official portals.
"""

CATALOG = {
  "BMW": {
    "models": {
      "Série 1": ["116", "118i", "118d", "120", "120d", "M135"],
      "Série 2": ["216", "218i", "218d", "220i", "220d", "225e", "230i", "M240i"],
      "Série 3": ["318i", "318d", "320i", "320d", "320e", "330i", "330d", "330e", "M340i", "M3"],
      "Série 4": ["420i", "420d", "430i", "430d", "M440i", "M4"],
      "Série 5": ["520i", "520d", "530e", "550e", "i5 eDrive40", "i5 M60", "M5"],
      "X1": ["sDrive18i", "sDrive18d", "xDrive25e", "xDrive30e", "iX1 eDrive20", "iX1 xDrive30"],
      "X2": ["sDrive20i", "xDrive20d", "iX2 eDrive20", "iX2 xDrive30"],
      "X3": ["20d", "30e", "M50", "iX3"],
      "X5": ["xDrive30d", "xDrive40i", "xDrive50e", "M60i", "X5 M"],
      "i4": ["eDrive35", "eDrive40", "xDrive40", "M60"],
      "i5": ["eDrive40", "xDrive40", "M60"],
      "iX": ["xDrive45", "xDrive60", "M70"],
    }
  },
  "Mercedes-Benz": {
    "models": {
      "Classe A": ["A 180", "A 200", "A 220 d", "A 250 e", "AMG A 35", "AMG A 45"],
      "Classe C": ["C 200", "C 220 d", "C 300 e", "C 300 de", "AMG C 43", "AMG C 63"],
      "Classe E": ["E 200", "E 220 d", "E 300 e", "E 300 de", "AMG E 53"],
      "CLA": ["CLA 180", "CLA 200", "CLA 220 d", "CLA 250 e", "AMG CLA 35", "AMG CLA 45"],
      "GLA": ["GLA 180", "GLA 200", "GLA 220 d", "GLA 250 e", "AMG GLA 35", "AMG GLA 45"],
      "GLC": ["GLC 220 d", "GLC 300 e", "GLC 300 de", "GLC 450 d", "AMG GLC 43", "AMG GLC 63"],
      "GLE": ["GLE 300 d", "GLE 350 de", "GLE 450", "GLE 450 d", "AMG GLE 53", "AMG GLE 63"],
      "EQA": ["EQA 250+", "EQA 300 4MATIC", "EQA 350 4MATIC"],
      "EQB": ["EQB 250+", "EQB 300 4MATIC", "EQB 350 4MATIC"],
      "EQE SUV": ["EQE 300", "EQE 350+", "EQE 500 4MATIC", "AMG EQE 53"],
    }
  },
  "Audi": {
    "models": {
      "A3": ["30 TFSI", "35 TFSI", "35 TDI", "40 TFSI e", "S3", "RS 3"],
      "A4": ["35 TFSI", "40 TDI", "45 TFSI", "S4", "RS 4"],
      "A5": ["TFSI", "TDI", "e-hybrid", "S5"],
      "A6": ["40 TDI", "45 TDI", "50 TFSI e", "55 TFSI e", "S6", "RS 6"],
      "A6 e-tron": ["performance", "quattro", "S6 e-tron"],
      "Q3": ["35 TFSI", "35 TDI", "45 TFSI e", "RS Q3"],
      "Q4 e-tron": ["40 e-tron", "45 e-tron", "45 quattro", "55 quattro"],
      "Q5": ["40 TDI", "50 TFSI e", "55 TFSI e", "SQ5"],
      "Q6 e-tron": ["performance", "quattro", "SQ6 e-tron"],
      "Q7": ["45 TDI", "50 TDI", "55 TFSI", "60 TFSI e", "SQ7"],
    }
  },
  "Volvo": {
    "models": {
      "EX30": ["Single Motor", "Single Motor Extended Range", "Twin Motor Performance"],
      "EX40": ["Single Motor", "Single Motor Extended Range", "Twin Motor"],
      "EC40": ["Single Motor", "Single Motor Extended Range", "Twin Motor"],
      "EX60": ["Single Motor", "Twin Motor"],
      "XC40": ["B3", "B4", "T4 Recharge", "T5 Recharge"],
      "XC60": ["B4", "B5", "T6 AWD Plug-in", "T8 AWD Plug-in"],
      "XC90": ["B5", "B6", "T8 AWD Plug-in"],
      "V60": ["B4", "T6 AWD Plug-in", "T8 AWD Plug-in"],
      "V90": ["B4", "B5", "T8 AWD Plug-in"],
    }
  },
  "Porsche": {
    "models": {
      "718 Cayman": ["2.0", "S", "GTS 4.0", "GT4", "GT4 RS"],
      "911": ["Carrera", "Carrera S", "Carrera 4", "Carrera 4S", "GTS", "Turbo", "Turbo S", "GT3"],
      "Macan": ["Macan", "Macan S", "Macan GTS", "Macan Electric", "Macan 4 Electric", "Macan Turbo Electric"],
      "Cayenne": ["Cayenne", "Cayenne E-Hybrid", "Cayenne S E-Hybrid", "Cayenne Turbo E-Hybrid"],
      "Taycan": ["Taycan", "4S", "GTS", "Turbo", "Turbo S"],
    }
  },
  "Volkswagen": {"models":{"Golf":["1.0 TSI","1.5 eTSI","2.0 TDI","eHybrid","GTE","GTI","R"],"Passat":["1.5 eTSI","2.0 TDI","eHybrid"],"Tiguan":["1.5 eTSI","2.0 TDI","eHybrid"],"ID.3":["Pure","Pro","Pro S","GTX"],"ID.4":["Pure","Pro","GTX"],"ID.7":["Pro","Pro S","GTX"]}},
  "Škoda": {"models":{"Octavia":["1.5 TSI","1.5 eTSI","2.0 TDI","iV","RS"],"Superb":["1.5 eTSI","2.0 TDI","iV"],"Kodiaq":["1.5 eTSI","2.0 TDI","iV"],"Enyaq":["60","85","85x","RS"]}},
  "SEAT": {"models":{"Leon":["1.0 TSI","1.5 eTSI","2.0 TDI","e-HYBRID"],"Ateca":["1.0 TSI","1.5 TSI","2.0 TDI"],"Arona":["1.0 TSI","1.5 TSI"]}},
  "CUPRA": {"models":{"Leon":["1.5 eTSI","e-HYBRID","VZ"],"Formentor":["1.5 eTSI","2.0 TSI","e-HYBRID","VZ"],"Born":["59 kWh","79 kWh","VZ"],"Tavascan":["Endurance","VZ"]}},
  "Toyota": {"models":{"Corolla":["1.8 Hybrid","2.0 Hybrid"],"C-HR":["1.8 Hybrid","2.0 Hybrid","2.0 Plug-in Hybrid"],"RAV4":["Hybrid","Plug-in Hybrid"],"bZ4X":["FWD","AWD"]}},
  "Lexus": {"models":{"LBX":["Hybrid"],"UX":["300h","300e"],"NX":["350h","450h+"],"RX":["350h","450h+","500h"],"RZ":["300e","450e","550e"]}},
  "Tesla": {"models":{"Model 3":["RWD","Long Range RWD","Long Range AWD","Performance"],"Model Y":["RWD","Long Range RWD","Long Range AWD","Performance"]}},
  "Ford": {"models":{"Focus":["EcoBoost","EcoBlue"],"Kuga":["EcoBoost","FHEV","PHEV"],"Explorer":["Standard Range","Extended Range"],"Capri":["Standard Range","Extended Range"]}},
  "Hyundai": {"models":{"Kona":["1.0 T-GDi","Hybrid","Electric"],"Tucson":["T-GDi","Hybrid","Plug-in Hybrid"],"IONIQ 5":["63 kWh","84 kWh","N"],"IONIQ 6":["Standard Range","Long Range"]}},
  "Kia": {"models":{"Niro":["Hybrid","Plug-in Hybrid","EV"],"Sportage":["T-GDi","Hybrid","Plug-in Hybrid"],"EV3":["Standard Range","Long Range"],"EV6":["RWD","AWD","GT"],"EV9":["RWD","AWD","GT"]}},
  "Nissan": {"models":{"Juke":["DIG-T","Hybrid"],"Qashqai":["mild hybrid","e-POWER"],"X-Trail":["mild hybrid","e-POWER"],"Ariya":["63 kWh","87 kWh","e-4ORCE"]}},
  "Renault": {"models":{"Clio":["TCe","E-Tech full hybrid"],"Captur":["TCe","E-Tech full hybrid"],"Austral":["mild hybrid","E-Tech full hybrid"],"Scenic E-Tech":["60 kWh","87 kWh"],"Megane E-Tech":["60 kWh"]}},
  "Peugeot": {"models":{"208":["PureTech","Hybrid","E-208"],"308":["PureTech","Hybrid","Plug-in Hybrid","E-308"],"3008":["Hybrid","Plug-in Hybrid","E-3008"],"5008":["Hybrid","Plug-in Hybrid","E-5008"]}},
  "Citroën": {"models":{"C3":["Turbo","Hybrid","ë-C3"],"C4":["Turbo","Hybrid","ë-C4"],"C5 Aircross":["Hybrid","Plug-in Hybrid","Electric"]}},
  "Opel": {"models":{"Corsa":["Gasolina","Hybrid","Electric"],"Astra":["Gasolina","Hybrid","Plug-in Hybrid","Electric"],"Grandland":["Hybrid","Plug-in Hybrid","Electric"]}},
}

BODY_STYLES = [
  ("all","Qualquer carroçaria"),
  ("hatchback","Hatchback"),
  ("sedan","Sedan / Berlina"),
  ("station","Station Wagon / Carrinha"),
  ("suv","SUV"),
  ("coupe","Coupé"),
  ("cabrio","Cabrio / Roadster"),
  ("mpv","Monovolume"),
]

# Generic and manufacturer-specific aliases used to broaden the same search.
BODY_ALIASES = {
  "station": {
    "_generic":["station wagon","carrinha","estate","sw"],
    "BMW":["Touring"],
    "Audi":["Avant"],
    "Mercedes-Benz":["Estate","Station"],
    "Volvo":["V"],
    "Volkswagen":["Variant"],
    "Škoda":["Combi"],
    "SEAT":["Sportstourer","ST"],
    "CUPRA":["Sportstourer"],
    "Peugeot":["SW"],
    "Opel":["Sports Tourer"],
  },
  "sedan":{"_generic":["sedan","berlina","limousine"],"BMW":["Sedan"],"Audi":["Limousine"],"Mercedes-Benz":["Limousine"]},
  "suv":{"_generic":["SUV","crossover"]},
  "hatchback":{"_generic":["hatchback","compacto"]},
  "coupe":{"_generic":["coupe","coupé"]},
  "cabrio":{"_generic":["cabrio","cabriolet","roadster","convertible"]},
  "mpv":{"_generic":["mpv","monovolume"]},
}

def brands():
    return sorted(CATALOG.keys())

def models_for(make):
    return sorted(CATALOG.get(make,{}).get("models",{}).keys())

def variants_for(make,model):
    return CATALOG.get(make,{}).get("models",{}).get(model,[])

def body_aliases(make,body):
    if not body or body=="all": return []
    d=BODY_ALIASES.get(body,{})
    return list(dict.fromkeys((d.get(make) or []) + (d.get("_generic") or [])))

def canonical_query(make="",model="",variant="",body="all"):
    parts=[x.strip() for x in (make,model,variant) if x and x.strip()]
    # Put the manufacturer-native body term first to maximize official-portal recall.
    aliases=body_aliases(make,body)
    if aliases: parts.append(aliases[0])
    return " ".join(parts)

def query_variants(make="",model="",variant="",body="all"):
    base=" ".join(x.strip() for x in (make,model,variant) if x and x.strip())
    aliases=body_aliases(make,body)
    if not aliases:return [base]
    return [base+" "+a for a in aliases[:4]]
