"""Catálogo de la librería del Ejercicio guiado 02.

El microservicio SOAP/JSON reutiliza los mismos ISBN, títulos, conceptos
IaaS/PaaS/SaaS/FaaS e imágenes de portada. No altera las tablas del monolito.
"""

CLOUD_MODELS = (
    {
        "name": "IaaS",
        "fullName": "Infrastructure as a Service",
        "description": "Infrastructure as a Service",
    },
    {
        "name": "PaaS",
        "fullName": "Platform as a Service",
        "description": "Platform as a Service",
    },
    {
        "name": "SaaS",
        "fullName": "Software as a Service",
        "description": "Software as a Service",
    },
    {
        "name": "FaaS",
        "fullName": "Function as a Service",
        "description": "Function as a Service",
    },
)

# IDs alineados con el INSERT de concepts en ejercicio02/library/db/02_seed_30_per_table.sql
CONCEPT_IDS = {
    "IaaS": 1,
    "PaaS": 2,
    "SaaS": 3,
    "FaaS": 4,
    "Bucket": 5,
    "Public Cloud": 6,
    "Private Cloud": 7,
    "Hybrid Cloud": 8,
    "Multicloud": 9,
    "Serverless": 10,
    "Memoria": 11,
    "Identidad": 12,
    "Código limpio": 13,
    "Civilización": 14,
    "Microservicios": 15,
    "Contenedor": 16,
    "Orquestación": 17,
    "CI/CD": 18,
    "Observabilidad": 19,
    "Latencia": 20,
    "Throughput": 21,
    "Consistencia": 22,
    "Disponibilidad": 23,
    "Partición": 24,
    "Normalización": 25,
    "Transacción": 26,
    "Índice": 27,
    "Caché": 28,
    "API Gateway": 29,
    "Balanceo de carga": 30,
}

BOOKS = [
    {
        "isbn": "9780134444245",
        "title": "Cloud Computing: Concepts, Technology & Architecture",
        "publicationYear": 2013,
        "price": 54.90,
        "stock": 15,
        "format": "Tapa dura",
        "category": "Computación en la nube",
        "description": "Modelos, tecnologías y arquitectura de la computación en la nube.",
        "authors": ["Thomas Erl", "Rajkumar Buyya"],
    },
    {
        "isbn": "9780307474728",
        "title": "Cien años de soledad",
        "publicationYear": 1967,
        "price": 24.90,
        "stock": 12,
        "format": "Tapa blanda",
        "category": "Literatura",
        "description": "La saga de los Buendía en el pueblo de Macondo.",
        "authors": ["Gabriel García Márquez"],
    },
    {
        "isbn": "9780132350884",
        "title": "Clean Code",
        "publicationYear": 2008,
        "price": 39.90,
        "stock": 8,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Guía para escribir código legible y fácil de mantener.",
        "authors": ["Robert C. Martin"],
    },
    {
        "isbn": "9780062316097",
        "title": "Sapiens",
        "publicationYear": 2011,
        "price": 29.90,
        "stock": 10,
        "format": "Digital",
        "category": "Ciencias sociales",
        "description": "Recorrido por la historia de la humanidad.",
        "authors": ["Yuval Noah Harari"],
    },
    {
        "isbn": "9780307389732",
        "title": "El amor en los tiempos del cólera",
        "publicationYear": 1985,
        "price": 22.50,
        "stock": 9,
        "format": "Tapa blanda",
        "category": "Literatura",
        "description": "Una historia de amor que recorre más de medio siglo.",
        "authors": ["Gabriel García Márquez"],
    },
    {
        "isbn": "9781501117015",
        "title": "La casa de los espíritus",
        "publicationYear": 1982,
        "price": 21.00,
        "stock": 7,
        "format": "Bolsillo",
        "category": "Literatura",
        "description": "Tres generaciones de la familia Trueba en Chile.",
        "authors": ["Isabel Allende"],
    },
    {
        "isbn": "9788437604572",
        "title": "Rayuela",
        "publicationYear": 1963,
        "price": 23.40,
        "stock": 6,
        "format": "Rústica",
        "category": "Literatura",
        "description": "Novela abierta que puede leerse en varios órdenes.",
        "authors": ["Julio Cortázar"],
    },
    {
        "isbn": "9780802133908",
        "title": "Pedro Páramo",
        "publicationYear": 1955,
        "price": 18.90,
        "stock": 11,
        "format": "Bolsillo",
        "category": "Literatura",
        "description": "Juan Preciado llega a Comala en busca de su padre.",
        "authors": ["Juan Rulfo"],
    },
    {
        "isbn": "9780451524935",
        "title": "1984",
        "publicationYear": 1949,
        "price": 16.50,
        "stock": 14,
        "format": "Bolsillo",
        "category": "Literatura",
        "description": "Oceanía, el Gran Hermano y la vigilancia total.",
        "authors": ["George Orwell"],
    },
    {
        "isbn": "9780135957059",
        "title": "The Pragmatic Programmer",
        "publicationYear": 2019,
        "price": 44.00,
        "stock": 5,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Oficio, herramientas y criterio del programador profesional.",
        "authors": ["Andrew Hunt", "David Thomas"],
    },
    {
        "isbn": "9781449373320",
        "title": "Designing Data-Intensive Applications",
        "publicationYear": 2017,
        "price": 49.90,
        "stock": 8,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Sistemas de datos: replicación, partición y consenso.",
        "authors": ["Martin Kleppmann"],
    },
    {
        "isbn": "9781617293726",
        "title": "Kubernetes in Action",
        "publicationYear": 2018,
        "price": 47.50,
        "stock": 4,
        "format": "Tapa blanda",
        "category": "Computación en la nube",
        "description": "Orquestación de contenedores con Kubernetes.",
        "authors": ["Marko Luksa"],
    },
    {
        "isbn": "9781491929124",
        "title": "Site Reliability Engineering",
        "publicationYear": 2016,
        "price": 52.00,
        "stock": 6,
        "format": "Tapa dura",
        "category": "Computación en la nube",
        "description": "Cómo Google opera sistemas en producción.",
        "authors": ["Betsy Beyer"],
    },
    {
        "isbn": "9781942788294",
        "title": "The Phoenix Project",
        "publicationYear": 2013,
        "price": 27.00,
        "stock": 10,
        "format": "Tapa blanda",
        "category": "Negocios",
        "description": "Novela sobre DevOps y la recuperación de un proyecto de TI.",
        "authors": ["Gene Kim"],
    },
    {
        "isbn": "9780134757599",
        "title": "Refactoring",
        "publicationYear": 2018,
        "price": 46.80,
        "stock": 5,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Cómo mejorar el diseño de código existente.",
        "authors": ["Martin Fowler"],
    },
    {
        "isbn": "9780321125217",
        "title": "Domain-Driven Design",
        "publicationYear": 2003,
        "price": 55.00,
        "stock": 3,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Modelar software a partir del lenguaje del negocio.",
        "authors": ["Eric Evans"],
    },
    {
        "isbn": "9788420412146",
        "title": "Don Quijote de la Mancha",
        "publicationYear": 1605,
        "price": 19.90,
        "stock": 20,
        "format": "Edición de lujo",
        "category": "Literatura",
        "description": "Las andanzas de Alonso Quijano y Sancho Panza.",
        "authors": ["Miguel de Cervantes"],
    },
    {
        "isbn": "9780802130303",
        "title": "Ficciones",
        "publicationYear": 1944,
        "price": 17.50,
        "stock": 9,
        "format": "Bolsillo",
        "category": "Literatura",
        "description": "Cuentos de laberintos, bibliotecas y destinos.",
        "authors": ["Jorge Luis Borges"],
    },
    {
        "isbn": "9780385420174",
        "title": "Como agua para chocolate",
        "publicationYear": 1989,
        "price": 18.00,
        "stock": 8,
        "format": "Tapa blanda",
        "category": "Literatura",
        "description": "Tita y las recetas que disparan la emoción en su familia.",
        "authors": ["Laura Esquivel"],
    },
    {
        "isbn": "9789681603021",
        "title": "El laberinto de la soledad",
        "publicationYear": 1950,
        "price": 16.80,
        "stock": 7,
        "format": "Rústica",
        "category": "Ciencias sociales",
        "description": "Ensayo sobre la identidad mexicana.",
        "authors": ["Octavio Paz"],
    },
    {
        "isbn": "9780553380163",
        "title": "A Brief History of Time",
        "publicationYear": 1988,
        "price": 20.00,
        "stock": 12,
        "format": "Tapa blanda",
        "category": "Ciencias exactas",
        "description": "Del Big Bang a los agujeros negros, para un lector general.",
        "authors": ["Stephen Hawking"],
    },
    {
        "isbn": "9780374533557",
        "title": "Thinking, Fast and Slow",
        "publicationYear": 2011,
        "price": 26.90,
        "stock": 9,
        "format": "Tapa blanda",
        "category": "Psicología",
        "description": "Dos sistemas de pensamiento y sus sesgos.",
        "authors": ["Daniel Kahneman"],
    },
    {
        "isbn": "9780307887894",
        "title": "The Lean Startup",
        "publicationYear": 2011,
        "price": 25.00,
        "stock": 11,
        "format": "Digital",
        "category": "Negocios",
        "description": "Construir un negocio con hipótesis, medición y aprendizaje.",
        "authors": ["Eric Ries"],
    },
    {
        "isbn": "9780735211292",
        "title": "Atomic Habits",
        "publicationYear": 2018,
        "price": 24.00,
        "stock": 16,
        "format": "Tapa dura",
        "category": "Desarrollo personal",
        "description": "Cambios pequeños que se acumulan en hábitos duraderos.",
        "authors": ["James Clear"],
    },
    {
        "isbn": "9780465050659",
        "title": "The Design of Everyday Things",
        "publicationYear": 2013,
        "price": 28.50,
        "stock": 6,
        "format": "Tapa blanda",
        "category": "Arte",
        "description": "Por qué algunos objetos se entienden solos y otros no.",
        "authors": ["Don Norman"],
    },
    {
        "isbn": "9780262033848",
        "title": "Introduction to Algorithms",
        "publicationYear": 2009,
        "price": 89.00,
        "stock": 4,
        "format": "Tapa dura",
        "category": "Matemáticas",
        "description": "Diseño y análisis clásico de algoritmos.",
        "authors": ["Thomas H. Cormen"],
    },
    {
        "isbn": "9780132126953",
        "title": "Computer Networks",
        "publicationYear": 2010,
        "price": 78.00,
        "stock": 3,
        "format": "Tapa dura",
        "category": "Ingeniería",
        "description": "Principios y protocolos de las redes de computadoras.",
        "authors": ["Andrew S. Tanenbaum"],
    },
    {
        "isbn": "9781118063330",
        "title": "Operating System Concepts",
        "publicationYear": 2012,
        "price": 82.00,
        "stock": 4,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Procesos, memoria, archivos y concurrencia.",
        "authors": ["Abraham Silberschatz"],
    },
    {
        "isbn": "9780073523323",
        "title": "Database System Concepts",
        "publicationYear": 2010,
        "price": 84.50,
        "stock": 5,
        "format": "Tapa dura",
        "category": "Tecnología",
        "description": "Modelo relacional, transacciones e índices.",
        "authors": ["Abraham Silberschatz"],
    },
    {
        "isbn": "9781593279288",
        "title": "Python Crash Course",
        "publicationYear": 2019,
        "price": 32.00,
        "stock": 13,
        "format": "Tapa blanda",
        "category": "Educación",
        "description": "Introducción práctica a Python con proyectos.",
        "authors": ["Eric Matthes"],
    },
]

# Filas de book_concepts del seed del EG02 (definición por libro).
BOOK_CONCEPTS = [
    ("9780134444245", "IaaS", "Infraestructura de cómputo, almacenamiento y red entregada como servicio medible.", "3", 45),
    ("9780134444245", "PaaS", "Plataforma administrada para desarrollar y operar aplicaciones sin gestionar el sistema operativo.", "3", 52),
    ("9780134444245", "SaaS", "Aplicación completa entregada por red, por lo general desde un navegador.", "3", 58),
    ("9780134444245", "FaaS", "Funciones disparadas por eventos, con cobro por invocación y tiempo de ejecución.", "4", 71),
    ("9780134444245", "Bucket", "Contenedor lógico de objetos donde se guardan archivos y metadatos.", "6", 118),
    ("9780134444245", "Public Cloud", "Servicios elásticos compartidos y operados por un proveedor externo.", "2", 21),
    ("9780134444245", "Private Cloud", "Capacidad cloud dedicada a una organización, en sitio o hospedada.", "2", 27),
    ("9780134444245", "Hybrid Cloud", "Integración de nube privada y pública para mover cargas o ampliar capacidad.", "2", 33),
    ("9780134444245", "Multicloud", "Uso de más de un proveedor para reducir dependencia y ganar resiliencia.", "2", 38),
    ("9780134444245", "Serverless", "El proveedor administra los servidores; el equipo se concentra en eventos y código.", "4", 80),
    ("9780307474728", "Memoria", "La memoria colectiva de Macondo conserva el pasado familiar y social.", "1", 12),
    ("9780132350884", "Código limpio", "Código expresivo, simple y fácil de mantener por otras personas.", "1", 8),
    ("9780062316097", "Civilización", "Organización humana basada en cooperación, mitos compartidos e instituciones.", "2", 40),
    ("9780062316097", "Identidad", "Construcción cultural de quiénes somos como especie y sociedad.", "4", 90),
    ("9781617293726", "Contenedor", "Unidad portable que empaca la aplicación de Kubernetes junto con sus dependencias.", "2", 19),
    ("9781617293726", "Orquestación", "Kubernetes programa réplicas, reinicios y escalado de contenedores.", "1", 7),
    ("9781449373320", "Consistencia", "Garantías sobre cuándo los nodos de un almacén de datos coinciden.", "9", 221),
    ("9780073523323", "Normalización", "Diseño de tablas que evita redundancia y anomalías de actualización.", "7", 278),
    ("9780073523323", "Transacción", "Conjunto de operaciones que se confirman o se deshacen juntas.", "14", 541),
    ("9780073523323", "Índice", "Estructura auxiliar que acelera la búsqueda por ISBN, título u otras claves.", "11", 412),
]

# Escenarios pedagógicos del EG03 (clasificar como IaaS/PaaS/SaaS/FaaS) sobre libros reales.
SOAP_SCENARIOS = [
    {
        "concept_id": 101,
        "concept_name": "Máquinas virtuales",
        "definition": (
            "Infraestructura con máquinas virtuales, almacenamiento y redes "
            "para instalar el propio sistema operativo."
        ),
        "isbn": "9780134444245",
        "book_title": "Cloud Computing: Concepts, Technology & Architecture",
        "category_name": "Computación en la nube",
    },
    {
        "concept_id": 102,
        "concept_name": "Plataforma de despliegue",
        "definition": (
            "Desplegar la aplicación web sin administrar directamente "
            "servidores ni sistemas operativos."
        ),
        "isbn": "9780134444245",
        "book_title": "Cloud Computing: Concepts, Technology & Architecture",
        "category_name": "Computación en la nube",
    },
    {
        "concept_id": 103,
        "concept_name": "Correo en el navegador",
        "definition": (
            "Los empleados utilizan una aplicación de correo electrónico "
            "desde el navegador con suscripción mensual."
        ),
        "isbn": "9780134444245",
        "book_title": "Cloud Computing: Concepts, Technology & Architecture",
        "category_name": "Computación en la nube",
    },
    {
        "concept_id": 104,
        "concept_name": "Función serverless",
        "definition": (
            "Ejecutar una función automáticamente cada vez que un usuario "
            "suba una imagen al almacenamiento Cloud."
        ),
        "isbn": "9780134444245",
        "book_title": "Cloud Computing: Concepts, Technology & Architecture",
        "category_name": "Computación en la nube",
    },
]


def cover_path(isbn):
    return f"/covers/{isbn}.svg"


def stored_cover_name(isbn):
    return f"cover-{isbn}.png"


def book_by_isbn(isbn):
    for book in BOOKS:
        if book["isbn"] == isbn:
            return book
    return None


def soap_catalog():
    """Conceptos que clasifica el módulo SOAP: catálogo EG02 + escenarios."""
    rows = []
    by_isbn = {book["isbn"]: book for book in BOOKS}
    for isbn, name, definition, chapter, page in BOOK_CONCEPTS:
        book = by_isbn[isbn]
        rows.append(
            {
                "concept_id": CONCEPT_IDS[name],
                "concept_name": name,
                "definition": definition,
                "isbn": isbn,
                "book_title": book["title"],
                "category_name": book["category"],
                "chapter": chapter,
                "page_number": page,
            }
        )
    rows.extend(dict(item) for item in SOAP_SCENARIOS)
    return rows


def books_with_concepts(extra_books=None):
    by_isbn = {}
    for book in BOOKS:
        item = dict(book)
        item["coverUrl"] = cover_path(book["isbn"])
        item["concepts"] = []
        by_isbn[book["isbn"]] = item
    for isbn, name, definition, chapter, page in BOOK_CONCEPTS:
        by_isbn[isbn]["concepts"].append(
            {
                "conceptId": CONCEPT_IDS[name],
                "name": name,
                "definition": definition,
                "chapter": chapter,
                "pageNumber": page,
            }
        )
    for book in extra_books or []:
        by_isbn[book["isbn"]] = book
    return list(by_isbn.values())


def cloud_concepts_payload():
    by_isbn = {book["isbn"]: book for book in BOOKS}
    grouped = {model["name"]: {**model, "books": []} for model in CLOUD_MODELS}
    for isbn, name, definition, chapter, page in BOOK_CONCEPTS:
        if name not in grouped:
            continue
        book = by_isbn[isbn]
        grouped[name]["books"].append(
            {
                "isbn": isbn,
                "title": book["title"],
                "category": book["category"],
                "authors": list(book["authors"]),
                "description": book["description"],
                "definition": definition,
                "chapter": chapter,
                "pageNumber": page,
                "coverUrl": cover_path(isbn),
            }
        )
    return [grouped[model["name"]] for model in CLOUD_MODELS]


def books_with_images(extra_books=None):
    items = []
    for book in BOOKS:
        isbn = book["isbn"]
        items.append(
            {
                "isbn": isbn,
                "title": book["title"],
                "authors": list(book["authors"]),
                "category": book["category"],
                "coverUrl": cover_path(isbn),
                "images": [
                    {
                        "url": cover_path(isbn),
                        "storedName": stored_cover_name(isbn),
                        "alt": f"Portada de {book['title']}",
                        "mimeType": "image/svg+xml",
                        "isCover": True,
                    }
                ],
            }
        )
    for book in extra_books or []:
        isbn = book["isbn"]
        items.append(
            {
                "isbn": isbn,
                "title": book.get("title") or "",
                "authors": book.get("authors") or [],
                "category": book.get("category") or "",
                "coverUrl": book.get("coverUrl") or "",
                "images": book.get("images") or [],
            }
        )
    return items
