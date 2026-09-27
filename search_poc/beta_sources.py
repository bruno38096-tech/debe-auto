"""National source catalog for DEBE Search beta.

The beta intentionally keeps sources independent from the current DEBE app.
Each source is a public official brand/dealer inventory or, for Standvirtual,
a marketplace benchmark.
"""

SOURCES = [
    # Premium / German brands
    {"key":"bmw_new","name":"BMW Portugal — novos","domain":"bmw.pt","url":"https://www.bmw.pt/pt/all-models.html","kinds":["new_stock"],"official":True},
    {"key":"bmw_premium","name":"BMW Premium Selection","domain":"bmwpremiumselection.bmw.pt","url":"https://bmwpremiumselection.bmw.pt/","kinds":["used_certified"],"official":True},
    {"key":"bmw_caetano_new","name":"BMW / Caetano — novos em stock","domain":"caetano.pt","url":"https://caetano.pt/bmw/carros-novos/","kinds":["new_stock"],"official":True},
    {"key":"mercedes_new","name":"Mercedes-Benz — veículos disponíveis","domain":"mercedes-benz.pt","url":"https://www.mercedes-benz.pt/passengercars/models.html","kinds":["new_stock"],"official":True},
    {"key":"mercedes_certified","name":"Mercedes-Benz Certified","domain":"usados.mercedes-benz.pt","url":"https://usados.mercedes-benz.pt/vehicles","kinds":["used_certified","demo_service"],"official":True},
    {"key":"audi_immediate","name":"Audi — Disponível Imediatamente","domain":"disponivel-imediatamente.audi.pt","url":"https://disponivel-imediatamente.audi.pt/search","kinds":["new_stock"],"official":True},
    {"key":"audi_used","name":"Audi Usados","domain":"usados.audi.pt","url":"https://usados.audi.pt/","kinds":["used_certified","used"],"official":True},
    {"key":"vw_new","name":"Volkswagen Portugal — novos","domain":"volkswagen.pt","url":"https://www.volkswagen.pt/","kinds":["new_stock"],"official":True},
    {"key":"seat_new","name":"SEAT Portugal — novos","domain":"seat.pt","url":"https://www.seat.pt/","kinds":["new_stock"],"official":True},
    {"key":"cupra_new","name":"CUPRA Portugal — novos","domain":"cupraofficial.pt","url":"https://www.cupraofficial.pt/","kinds":["new_stock"],"official":True},
    {"key":"skoda_new","name":"Škoda Portugal — novos","domain":"skoda.pt","url":"https://www.skoda.pt/","kinds":["new_stock"],"official":True},
    {"key":"dwa","name":"Das WeltAuto","domain":"dasweltauto.pt","url":"https://www.dasweltauto.pt/search","kinds":["used_certified","used"],"official":True},
    {"key":"porsche_finder","name":"Porsche Finder Portugal","domain":"finder.porsche.com","url":"https://finder.porsche.com/pt/pt-PT/search","kinds":["new_stock","demo_service","used_certified","used"],"official":True},
    {"key":"volvo_inventory","name":"Volvo — Inventário Nacional","domain":"volvocars.com","url":"https://www.volvocars.com/pt/inventory/","kinds":["new_stock"],"official":True},
    {"key":"volvo_selekt","name":"Volvo Selekt","domain":"volvocars.com","url":"https://www.volvocars.com/pt/l/used-cars/","kinds":["used_certified"],"official":True},

    # Other manufacturer official programmes / inventories
    {"key":"ford_new","name":"Ford Portugal — stock novo","domain":"ford.pt","url":"https://www.ford.pt/compra","kinds":["new_stock"],"official":True},
    {"key":"ford_approved","name":"Ford Aprovado","domain":"secure.ford.pt","url":"https://secure.ford.pt/compra/explore/ford-aprovado/results","kinds":["used_certified"],"official":True},
    {"key":"hyundai_new","name":"Hyundai Portugal — novos","domain":"hyundai.pt","url":"https://www.hyundai.pt/","kinds":["new_stock"],"official":True},
    {"key":"hyundai_goon","name":"Hyundai GO ON","domain":"usados.hyundai.pt","url":"https://usados.hyundai.pt/viaturas/inicio","kinds":["used_certified","used"],"official":True},
    {"key":"toyota_new","name":"Toyota Portugal — novos","domain":"toyota.pt","url":"https://www.toyota.pt/","kinds":["new_stock"],"official":True},
    {"key":"toyota_used","name":"Toyota Usados de Confiança","domain":"usados.toyota.pt","url":"https://usados.toyota.pt/viaturas/pesquisa","kinds":["used_certified","used"],"official":True},
    {"key":"lexus_new","name":"Lexus Portugal — novos","domain":"lexus.pt","url":"https://www.lexus.pt/","kinds":["new_stock"],"official":True},
    {"key":"lexus_select","name":"Lexus Select","domain":"usados.lexus.pt","url":"https://usados.lexus.pt/viaturas/inicio","kinds":["used_certified","used"],"official":True},
    {"key":"nissan_new","name":"Nissan Portugal — novos","domain":"nissan.pt","url":"https://www.nissan.pt/","kinds":["new_stock"],"official":True},
    {"key":"nissan_choice","name":"Nissan Intelligent Choice","domain":"nissan.pt","url":"https://www.nissan.pt/veiculos-usados.html","kinds":["used_certified"],"official":True},
    {"key":"renault_new","name":"Renault Portugal — novos","domain":"renault.pt","url":"https://www.renault.pt/","kinds":["new_stock"],"official":True},
    {"key":"renault_renew","name":"Renault / Renew — usados","domain":"renault.pt","url":"https://www.renault.pt/","kinds":["used_certified","used"],"official":True},
    {"key":"dacia_new","name":"Dacia Portugal — novos","domain":"dacia.pt","url":"https://www.dacia.pt/","kinds":["new_stock"],"official":True},
    {"key":"kia","name":"Kia Portugal","domain":"kia.com","url":"https://www.kia.com/pt/","kinds":["new_stock","used"],"official":True},
    {"key":"peugeot_new","name":"Peugeot Portugal — novos","domain":"peugeot.pt","url":"https://www.peugeot.pt/","kinds":["new_stock"],"official":True},
    {"key":"citroen_new","name":"Citroën Portugal — novos","domain":"citroen.pt","url":"https://www.citroen.pt/","kinds":["new_stock"],"official":True},
    {"key":"opel_new","name":"Opel Portugal — novos","domain":"opel.pt","url":"https://www.opel.pt/","kinds":["new_stock"],"official":True},
    {"key":"fiat_new","name":"Fiat Portugal — novos","domain":"fiat.pt","url":"https://www.fiat.pt/","kinds":["new_stock"],"official":True},
    {"key":"jeep_new","name":"Jeep Portugal — novos","domain":"jeep.pt","url":"https://www.jeep.pt/","kinds":["new_stock"],"official":True},
    {"key":"stellantis_you","name":"Stellantis &You","domain":"stellantisandyou.com","url":"https://www.stellantisandyou.com/pt/comprar-carros-usados","kinds":["new_stock","demo_service","km0","used"],"official":True},
    {"key":"spoticar","name":"SPOTICAR Portugal","domain":"spoticar.pt","url":"https://www.spoticar.pt/","kinds":["used_certified","used"],"official":True},
    {"key":"tesla","name":"Tesla Inventory Portugal","domain":"tesla.com","url":"https://www.tesla.com/pt_PT/inventory/new/m3","kinds":["new_stock","used"],"official":True},

    # Large official dealer groups / dealer networks
    {"key":"carclasse","name":"Carclasse","domain":"carclasse.pt","url":"https://www.carclasse.pt/stock-viaturas","kinds":["new_stock","demo_service","km0","used_certified","used"],"official":True},
    {"key":"santogal","name":"Santogal","domain":"santogal.pt","url":"https://www.santogal.pt/pt/search-page/","kinds":["new_stock","demo_service","km0","used","used_certified"],"official":True},
    {"key":"caetano","name":"Caetano","domain":"caetano.pt","url":"https://caetano.pt/","kinds":["new_stock","demo_service","km0","used","used_certified"],"official":True},
    {"key":"bmcar","name":"BMcar","domain":"bmcar.pt","url":"https://www.bmcar.pt/veiculos","kinds":["new_stock","demo_service","km0","used","used_certified"],"official":True},
    {"key":"mcoutinho","name":"MCoutinho","domain":"mcoutinho.pt","url":"https://www.mcoutinho.pt/pesquisa","kinds":["new_stock","demo_service","km0","used","used_certified"],"official":True},
    {"key":"filinto","name":"Filinto Mota","domain":"filintomota.pt","url":"https://www.filintomota.pt/carros-usados/","kinds":["demo_service","km0","used","used_certified"],"official":True},

    # Benchmark
    {"key":"standvirtual","name":"Standvirtual — benchmark","domain":"standvirtual.com","url":"https://www.standvirtual.com/carros","kinds":["new_stock","demo_service","km0","used"],"official":False},
]

CONDITION_LABELS = {
    "new_stock": "Novo / stock imediato",
    "demo_service": "Serviço / demonstração",
    "km0": "KM0 / seminovo",
    "used_certified": "Usado certificado",
    "used": "Usado",
    "unknown": "Por classificar",
}
