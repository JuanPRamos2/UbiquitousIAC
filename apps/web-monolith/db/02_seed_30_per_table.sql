BEGIN;

INSERT INTO formats (name, description) VALUES
    ('Tapa blanda', 'Edición impresa con cubierta flexible'),
    ('Tapa dura', 'Edición impresa con cubierta rígida'),
    ('Digital', 'Libro electrónico para lector o aplicación'),
    ('Audiolibro', 'Narración en audio'),
    ('Bolsillo', 'Formato compacto de bolsillo'),
    ('Edición de lujo', 'Encuadernación especial de colección'),
    ('Edición ilustrada', 'Incluye láminas e ilustraciones'),
    ('Edición anotada', 'Con notas y aparato crítico'),
    ('Cartoné', 'Cubierta de cartón rígido'),
    ('Rústica', 'Cubierta de papel o cartulina'),
    ('Kindle', 'Edición para Amazon Kindle'),
    ('EPUB', 'Libro electrónico en formato EPUB'),
    ('PDF', 'Documento digital en PDF'),
    ('MP3', 'Audiolibro en archivos de audio'),
    ('CD', 'Audiolibro en disco compacto'),
    ('Coleccionista', 'Tiraje limitado numerado'),
    ('Primera edición', 'Primera impresión de la obra'),
    ('Edición crítica', 'Texto establecido por especialistas'),
    ('Edición bilingüe', 'Texto en dos idiomas'),
    ('Folio', 'Formato grande de página'),
    ('Cuarto mayor', 'Formato intermedio de página'),
    ('Infantil cartoné', 'Pasta dura para lectores infantiles'),
    ('Braille', 'Edición en sistema Braille'),
    ('Libro-disco', 'Volumen acompañado de disco'),
    ('Impresión bajo demanda', 'Impreso al momento del pedido'),
    ('Grapado', 'Cuadernillo grapado'),
    ('Espiral', 'Encuadernación de anillas'),
    ('Revista encuadernada', 'Números reunidos en un tomo'),
    ('Bolsillo deluxe', 'Bolsillo con papel de mayor calidad'),
    ('Facsímil', 'Reproducción fiel de un original')
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, description) VALUES
    ('Literatura', 'Narrativa, novela y cuento'),
    ('Tecnología', 'Programación e ingeniería de software'),
    ('Ciencias sociales', 'Sociedad, cultura e historia'),
    ('Computación en la nube', 'Infraestructura y servicios cloud'),
    ('Ciencias exactas', 'Matemáticas y física'),
    ('Negocios', 'Administración, startups y economía'),
    ('Historia', 'Estudios y relatos históricos'),
    ('Filosofía', 'Pensamiento y ensayo filosófico'),
    ('Psicología', 'Comportamiento y cognición'),
    ('Arte', 'Artes visuales y diseño'),
    ('Poesía', 'Obra poética'),
    ('Teatro', 'Dramaturgia'),
    ('Biografías', 'Vida de personas notables'),
    ('Infantil', 'Lectores de primera infancia'),
    ('Juvenil', 'Literatura para adolescentes'),
    ('Medicina', 'Ciencias de la salud'),
    ('Derecho', 'Normas y jurisprudencia'),
    ('Educación', 'Pedagogía y didáctica'),
    ('Arquitectura', 'Diseño y espacio construido'),
    ('Gastronomía', 'Cocina y cultura alimentaria'),
    ('Viajes', 'Guías y crónicas de viaje'),
    ('Deportes', 'Práctica y cultura deportiva'),
    ('Música', 'Historia y teoría musical'),
    ('Cine', 'Estudios cinematográficos'),
    ('Periodismo', 'Crónica y reportaje'),
    ('Religión', 'Estudios de tradiciones religiosas'),
    ('Ecología', 'Medio ambiente y sostenibilidad'),
    ('Ingeniería', 'Ingenierías aplicadas'),
    ('Matemáticas', 'Álgebra, cálculo y fundamentos'),
    ('Desarrollo personal', 'Hábitos, productividad y bienestar')
ON CONFLICT (name) DO NOTHING;

INSERT INTO authors (full_name, biography) VALUES
    ('Gabriel García Márquez', 'Escritor colombiano, Premio Nobel de Literatura en 1982.'),
    ('Isabel Allende', 'Novelista chilena, autora de La casa de los espíritus.'),
    ('Robert C. Martin', 'Ingeniero de software y autor de Clean Code.'),
    ('Yuval Noah Harari', 'Historiador israelí, autor de Sapiens.'),
    ('Thomas Erl', 'Autor de arquitectura de servicios y computación en la nube.'),
    ('Rajkumar Buyya', 'Investigador en sistemas distribuidos y cloud computing.'),
    ('Julio Cortázar', 'Escritor argentino, autor de Rayuela.'),
    ('Juan Rulfo', 'Narrador mexicano, autor de Pedro Páramo.'),
    ('George Orwell', 'Novelista y ensayista británico, autor de 1984.'),
    ('Andrew Hunt', 'Coautor de The Pragmatic Programmer.'),
    ('David Thomas', 'Coautor de The Pragmatic Programmer.'),
    ('Martin Kleppmann', 'Investigador y autor de Designing Data-Intensive Applications.'),
    ('Marko Luksa', 'Ingeniero y autor de Kubernetes in Action.'),
    ('Betsy Beyer', 'Editora técnica de Site Reliability Engineering en Google.'),
    ('Gene Kim', 'Autor de The Phoenix Project y The Unicorn Project.'),
    ('Martin Fowler', 'Autor de Refactoring y ensayista de arquitectura de software.'),
    ('Eric Evans', 'Autor de Domain-Driven Design.'),
    ('Miguel de Cervantes', 'Escritor español, autor de Don Quijote de la Mancha.'),
    ('Jorge Luis Borges', 'Escritor argentino, autor de Ficciones.'),
    ('Laura Esquivel', 'Escritora mexicana, autora de Como agua para chocolate.'),
    ('Octavio Paz', 'Poeta y ensayista mexicano, Premio Nobel de Literatura.'),
    ('Stephen Hawking', 'Físico teórico, autor de A Brief History of Time.'),
    ('Daniel Kahneman', 'Psicólogo, Premio Nobel de Economía, autor de Thinking, Fast and Slow.'),
    ('Eric Ries', 'Emprendedor y autor de The Lean Startup.'),
    ('James Clear', 'Autor de Atomic Habits.'),
    ('Don Norman', 'Investigador de diseño, autor de The Design of Everyday Things.'),
    ('Thomas H. Cormen', 'Profesor de informática y coautor de Introduction to Algorithms.'),
    ('Andrew S. Tanenbaum', 'Profesor y autor de Computer Networks.'),
    ('Abraham Silberschatz', 'Autor de Operating System Concepts y Database System Concepts.'),
    ('Eric Matthes', 'Profesor y autor de Python Crash Course.')
ON CONFLICT (full_name) DO NOTHING;

INSERT INTO genres (name, description) VALUES
    ('Realismo mágico', 'Narrativa con lo fantástico integrado en lo cotidiano'),
    ('Novela', 'Obra narrativa extensa de ficción'),
    ('Programación', 'Desarrollo de software y buenas prácticas'),
    ('Historia', 'Relato e interpretación del pasado'),
    ('Computación en la nube', 'Infraestructura, plataformas y servicios cloud'),
    ('Ensayo', 'Texto argumentativo de no ficción'),
    ('Ciencia ficción', 'Ficción basada en hipótesis científicas'),
    ('Fantasía', 'Mundos y reglas imaginarias'),
    ('Misterio', 'Intriga y resolución de un enigma'),
    ('Romance', 'Relato centrado en vínculos afectivos'),
    ('Biografía', 'Relato de una vida'),
    ('Poesía', 'Composición en verso o prosa poética'),
    ('Drama', 'Conflicto teatral o narrativo intenso'),
    ('Thriller', 'Suspenso de ritmo alto'),
    ('Distopía', 'Sociedad futura opresiva o degradada'),
    ('Crónica', 'Relato de hechos con mirada periodística'),
    ('Divulgación científica', 'Ciencia explicada para un público amplio'),
    ('Arquitectura de software', 'Diseño y organización de sistemas'),
    ('DevOps', 'Cultura y prácticas de entrega continua'),
    ('Algoritmos', 'Diseño y análisis de algoritmos'),
    ('Redes', 'Comunicación entre computadoras'),
    ('Sistemas operativos', 'Gestión de recursos de cómputo'),
    ('Bases de datos', 'Modelado y administración de datos'),
    ('Productividad', 'Hábitos y métodos de trabajo'),
    ('Diseño', 'Diseño de productos y experiencias'),
    ('Economía', 'Decisiones, mercados e incentivos'),
    ('Política', 'Poder, Estado y ciudadanía'),
    ('Memorias', 'Relato en primera persona'),
    ('Aventura', 'Travesía y riesgo'),
    ('Clásicos', 'Obras de trayectoria canónica')
ON CONFLICT (name) DO NOTHING;

INSERT INTO concepts (name, description) VALUES
    ('IaaS', 'Infrastructure as a Service'),
    ('PaaS', 'Platform as a Service'),
    ('SaaS', 'Software as a Service'),
    ('FaaS', 'Function as a Service'),
    ('Bucket', 'Contenedor de objetos en almacenamiento cloud'),
    ('Public Cloud', 'Nube pública operada por un proveedor'),
    ('Private Cloud', 'Nube privada dedicada a una organización'),
    ('Hybrid Cloud', 'Combinación de nube pública y privada'),
    ('Multicloud', 'Uso coordinado de varios proveedores cloud'),
    ('Serverless', 'Ejecución sin administrar servidores'),
    ('Memoria', 'Facultad de conservar y recuperar experiencias'),
    ('Identidad', 'Conjunto de rasgos que distingue a una persona o comunidad'),
    ('Código limpio', 'Prácticas que favorecen código legible y mantenible'),
    ('Civilización', 'Sociedad humana con organización cultural y política'),
    ('Microservicios', 'Servicios pequeños que colaboran por red'),
    ('Contenedor', 'Empaquetado portable de una aplicación y sus dependencias'),
    ('Orquestación', 'Programación y reparación automática de contenedores'),
    ('CI/CD', 'Integración y entrega continuas'),
    ('Observabilidad', 'Métricas, registros y trazas para entender un sistema'),
    ('Latencia', 'Tiempo que tarda una operación en completarse'),
    ('Throughput', 'Cantidad de trabajo útil por unidad de tiempo'),
    ('Consistencia', 'Acuerdo sobre el estado de los datos'),
    ('Disponibilidad', 'Proporción de tiempo en que el servicio responde'),
    ('Partición', 'Corte de comunicación entre nodos de un sistema'),
    ('Normalización', 'Organización relacional que reduce redundancia'),
    ('Transacción', 'Unidad de trabajo atómica en una base de datos'),
    ('Índice', 'Estructura auxiliar para acelerar búsquedas'),
    ('Caché', 'Copia rápida de datos de acceso frecuente'),
    ('API Gateway', 'Punto de entrada unificado hacia varios servicios'),
    ('Balanceo de carga', 'Reparto de peticiones entre varias instancias')
ON CONFLICT (name) DO NOTHING;

INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
SELECT v.isbn, v.title, v.year, v.price, v.stock, f.id, c.id, v.description
FROM (VALUES
    ('9780134444245', 'Cloud Computing: Concepts, Technology & Architecture', 2013, 54.90, 15, 'Tapa dura', 'Computación en la nube', 'Modelos, tecnologías y arquitectura de la computación en la nube.'),
    ('9780307474728', 'Cien años de soledad', 1967, 24.90, 12, 'Tapa blanda', 'Literatura', 'La saga de los Buendía en el pueblo de Macondo.'),
    ('9780132350884', 'Clean Code', 2008, 39.90, 8, 'Tapa dura', 'Tecnología', 'Guía para escribir código legible y fácil de mantener.'),
    ('9780062316097', 'Sapiens', 2011, 29.90, 10, 'Digital', 'Ciencias sociales', 'Recorrido por la historia de la humanidad.'),
    ('9780307389732', 'El amor en los tiempos del cólera', 1985, 22.50, 9, 'Tapa blanda', 'Literatura', 'Una historia de amor que recorre más de medio siglo.'),
    ('9781501117015', 'La casa de los espíritus', 1982, 21.00, 7, 'Bolsillo', 'Literatura', 'Tres generaciones de la familia Trueba en Chile.'),
    ('9788437604572', 'Rayuela', 1963, 23.40, 6, 'Rústica', 'Literatura', 'Novela abierta que puede leerse en varios órdenes.'),
    ('9780802133908', 'Pedro Páramo', 1955, 18.90, 11, 'Bolsillo', 'Literatura', 'Juan Preciado llega a Comala en busca de su padre.'),
    ('9780451524935', '1984', 1949, 16.50, 14, 'Bolsillo', 'Literatura', 'Oceanía, el Gran Hermano y la vigilancia total.'),
    ('9780135957059', 'The Pragmatic Programmer', 2019, 44.00, 5, 'Tapa dura', 'Tecnología', 'Oficio, herramientas y criterio del programador profesional.'),
    ('9781449373320', 'Designing Data-Intensive Applications', 2017, 49.90, 8, 'Tapa dura', 'Tecnología', 'Sistemas de datos: replicación, partición y consenso.'),
    ('9781617293726', 'Kubernetes in Action', 2018, 47.50, 4, 'Tapa blanda', 'Computación en la nube', 'Orquestación de contenedores con Kubernetes.'),
    ('9781491929124', 'Site Reliability Engineering', 2016, 52.00, 6, 'Tapa dura', 'Computación en la nube', 'Cómo Google opera sistemas en producción.'),
    ('9781942788294', 'The Phoenix Project', 2013, 27.00, 10, 'Tapa blanda', 'Negocios', 'Novela sobre DevOps y la recuperación de un proyecto de TI.'),
    ('9780134757599', 'Refactoring', 2018, 46.80, 5, 'Tapa dura', 'Tecnología', 'Cómo mejorar el diseño de código existente.'),
    ('9780321125217', 'Domain-Driven Design', 2003, 55.00, 3, 'Tapa dura', 'Tecnología', 'Modelar software a partir del lenguaje del negocio.'),
    ('9788420412146', 'Don Quijote de la Mancha', 1605, 19.90, 20, 'Edición de lujo', 'Literatura', 'Las andanzas de Alonso Quijano y Sancho Panza.'),
    ('9780802130303', 'Ficciones', 1944, 17.50, 9, 'Bolsillo', 'Literatura', 'Cuentos de laberintos, bibliotecas y destinos.'),
    ('9780385420174', 'Como agua para chocolate', 1989, 18.00, 8, 'Tapa blanda', 'Literatura', 'Tita y las recetas que disparan la emoción en su familia.'),
    ('9789681603021', 'El laberinto de la soledad', 1950, 16.80, 7, 'Rústica', 'Ciencias sociales', 'Ensayo sobre la identidad mexicana.'),
    ('9780553380163', 'A Brief History of Time', 1988, 20.00, 12, 'Tapa blanda', 'Ciencias exactas', 'Del Big Bang a los agujeros negros, para un lector general.'),
    ('9780374533557', 'Thinking, Fast and Slow', 2011, 26.90, 9, 'Tapa blanda', 'Psicología', 'Dos sistemas de pensamiento y sus sesgos.'),
    ('9780307887894', 'The Lean Startup', 2011, 25.00, 11, 'Digital', 'Negocios', 'Construir un negocio con hipótesis, medición y aprendizaje.'),
    ('9780735211292', 'Atomic Habits', 2018, 24.00, 16, 'Tapa dura', 'Desarrollo personal', 'Cambios pequeños que se acumulan en hábitos duraderos.'),
    ('9780465050659', 'The Design of Everyday Things', 2013, 28.50, 6, 'Tapa blanda', 'Arte', 'Por qué algunos objetos se entienden solos y otros no.'),
    ('9780262033848', 'Introduction to Algorithms', 2009, 89.00, 4, 'Tapa dura', 'Matemáticas', 'Diseño y análisis clásico de algoritmos.'),
    ('9780132126953', 'Computer Networks', 2010, 78.00, 3, 'Tapa dura', 'Ingeniería', 'Principios y protocolos de las redes de computadoras.'),
    ('9781118063330', 'Operating System Concepts', 2012, 82.00, 4, 'Tapa dura', 'Tecnología', 'Procesos, memoria, archivos y concurrencia.'),
    ('9780073523323', 'Database System Concepts', 2010, 84.50, 5, 'Tapa dura', 'Tecnología', 'Modelo relacional, transacciones e índices.'),
    ('9781593279288', 'Python Crash Course', 2019, 32.00, 13, 'Tapa blanda', 'Educación', 'Introducción práctica a Python con proyectos.')
) AS v(isbn, title, year, price, stock, format_name, category_name, description)
JOIN formats f ON f.name = v.format_name
JOIN categories c ON c.name = v.category_name
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO book_authors (book_id, author_id)
SELECT b.id, a.id
FROM (VALUES
    ('9780134444245', 'Thomas Erl'),
    ('9780134444245', 'Rajkumar Buyya'),
    ('9780307474728', 'Gabriel García Márquez'),
    ('9780132350884', 'Robert C. Martin'),
    ('9780062316097', 'Yuval Noah Harari'),
    ('9780307389732', 'Gabriel García Márquez'),
    ('9781501117015', 'Isabel Allende'),
    ('9788437604572', 'Julio Cortázar'),
    ('9780802133908', 'Juan Rulfo'),
    ('9780451524935', 'George Orwell'),
    ('9780135957059', 'Andrew Hunt'),
    ('9780135957059', 'David Thomas'),
    ('9781449373320', 'Martin Kleppmann'),
    ('9781617293726', 'Marko Luksa'),
    ('9781491929124', 'Betsy Beyer'),
    ('9781942788294', 'Gene Kim'),
    ('9780134757599', 'Martin Fowler'),
    ('9780321125217', 'Eric Evans'),
    ('9788420412146', 'Miguel de Cervantes'),
    ('9780802130303', 'Jorge Luis Borges'),
    ('9780385420174', 'Laura Esquivel'),
    ('9789681603021', 'Octavio Paz'),
    ('9780553380163', 'Stephen Hawking'),
    ('9780374533557', 'Daniel Kahneman'),
    ('9780307887894', 'Eric Ries'),
    ('9780735211292', 'James Clear'),
    ('9780465050659', 'Don Norman'),
    ('9780262033848', 'Thomas H. Cormen'),
    ('9780132126953', 'Andrew S. Tanenbaum'),
    ('9781118063330', 'Abraham Silberschatz'),
    ('9780073523323', 'Abraham Silberschatz'),
    ('9781593279288', 'Eric Matthes')
) AS v(isbn, author_name)
JOIN books b ON b.isbn = v.isbn
JOIN authors a ON a.full_name = v.author_name
ON CONFLICT DO NOTHING;

INSERT INTO book_genres (book_id, genre_id)
SELECT b.id, g.id
FROM (VALUES
    ('9780134444245', 'Computación en la nube'),
    ('9780134444245', 'Ensayo'),
    ('9780307474728', 'Realismo mágico'),
    ('9780307474728', 'Novela'),
    ('9780132350884', 'Programación'),
    ('9780062316097', 'Historia'),
    ('9780062316097', 'Ensayo'),
    ('9780307389732', 'Novela'),
    ('9780307389732', 'Romance'),
    ('9781501117015', 'Realismo mágico'),
    ('9788437604572', 'Novela'),
    ('9780802133908', 'Novela'),
    ('9780451524935', 'Distopía'),
    ('9780135957059', 'Programación'),
    ('9781449373320', 'Arquitectura de software'),
    ('9781617293726', 'Computación en la nube'),
    ('9781491929124', 'DevOps'),
    ('9781942788294', 'DevOps'),
    ('9780134757599', 'Programación'),
    ('9780321125217', 'Arquitectura de software'),
    ('9788420412146', 'Clásicos'),
    ('9780802130303', 'Clásicos'),
    ('9780385420174', 'Realismo mágico'),
    ('9789681603021', 'Ensayo'),
    ('9780553380163', 'Divulgación científica'),
    ('9780374533557', 'Ensayo'),
    ('9780307887894', 'Productividad'),
    ('9780735211292', 'Productividad'),
    ('9780465050659', 'Diseño'),
    ('9780262033848', 'Algoritmos'),
    ('9780132126953', 'Redes'),
    ('9781118063330', 'Sistemas operativos'),
    ('9780073523323', 'Bases de datos'),
    ('9781593279288', 'Programación')
) AS v(isbn, genre_name)
JOIN books b ON b.isbn = v.isbn
JOIN genres g ON g.name = v.genre_name
ON CONFLICT DO NOTHING;

INSERT INTO book_concepts (book_id, concept_id, definition, chapter, page_number)
SELECT b.id, c.id, v.definition, v.chapter, v.page_number
FROM (VALUES
    ('9780134444245', 'IaaS', 'Infraestructura de cómputo, almacenamiento y red entregada como servicio medible.', '3', 45),
    ('9780134444245', 'PaaS', 'Plataforma administrada para desarrollar y operar aplicaciones sin gestionar el sistema operativo.', '3', 52),
    ('9780134444245', 'SaaS', 'Aplicación completa entregada por red, por lo general desde un navegador.', '3', 58),
    ('9780134444245', 'FaaS', 'Funciones disparadas por eventos, con cobro por invocación y tiempo de ejecución.', '4', 71),
    ('9780134444245', 'Bucket', 'Contenedor lógico de objetos donde se guardan archivos y metadatos.', '6', 118),
    ('9780134444245', 'Public Cloud', 'Servicios elásticos compartidos y operados por un proveedor externo.', '2', 21),
    ('9780134444245', 'Private Cloud', 'Capacidad cloud dedicada a una organización, en sitio o hospedada.', '2', 27),
    ('9780134444245', 'Hybrid Cloud', 'Integración de nube privada y pública para mover cargas o ampliar capacidad.', '2', 33),
    ('9780134444245', 'Multicloud', 'Uso de más de un proveedor para reducir dependencia y ganar resiliencia.', '2', 38),
    ('9780134444245', 'Serverless', 'El proveedor administra los servidores; el equipo se concentra en eventos y código.', '4', 80),
    ('9780307474728', 'Memoria', 'La memoria colectiva de Macondo conserva el pasado familiar y social.', '1', 12),
    ('9780132350884', 'Código limpio', 'Código expresivo, simple y fácil de mantener por otras personas.', '1', 8),
    ('9780062316097', 'Civilización', 'Organización humana basada en cooperación, mitos compartidos e instituciones.', '2', 40),
    ('9780062316097', 'Identidad', 'Construcción cultural de quiénes somos como especie y sociedad.', '4', 90),
    ('9781617293726', 'Contenedor', 'Unidad portable que empaca la aplicación de Kubernetes junto con sus dependencias.', '2', 19),
    ('9781617293726', 'Orquestación', 'Kubernetes programa réplicas, reinicios y escalado de contenedores.', '1', 7),
    ('9781449373320', 'Consistencia', 'Garantías sobre cuándo los nodos de un almacén de datos coinciden.', '9', 221),
    ('9780073523323', 'Normalización', 'Diseño de tablas que evita redundancia y anomalías de actualización.', '7', 278),
    ('9780073523323', 'Transacción', 'Conjunto de operaciones que se confirman o se deshacen juntas.', '14', 541),
    ('9780073523323', 'Índice', 'Estructura auxiliar que acelera la búsqueda por ISBN, título u otras claves.', '11', 412)
) AS v(isbn, concept_name, definition, chapter, page_number)
JOIN books b ON b.isbn = v.isbn
JOIN concepts c ON c.name = v.concept_name
ON CONFLICT (book_id, concept_id) DO UPDATE
    SET definition = EXCLUDED.definition,
        chapter = EXCLUDED.chapter,
        page_number = EXCLUDED.page_number;

INSERT INTO images (stored_name, alt_text, mime_type, byte_size)
SELECT
    'cover-' || v.isbn || '.png',
    'Portada de ' || b.title,
    'image/png',
    12000
FROM (VALUES
    ('9780134444245'),('9780307474728'),('9780132350884'),('9780062316097'),
    ('9780307389732'),('9781501117015'),('9788437604572'),('9780802133908'),
    ('9780451524935'),('9780135957059'),('9781449373320'),('9781617293726'),
    ('9781491929124'),('9781942788294'),('9780134757599'),('9780321125217'),
    ('9788420412146'),('9780802130303'),('9780385420174'),('9789681603021'),
    ('9780553380163'),('9780374533557'),('9780307887894'),('9780735211292'),
    ('9780465050659'),('9780262033848'),('9780132126953'),('9781118063330'),
    ('9780073523323'),('9781593279288')
) AS v(isbn)
JOIN books b ON b.isbn = v.isbn
ON CONFLICT (stored_name) DO NOTHING;

INSERT INTO book_images (book_id, image_id, is_cover)
SELECT b.id, i.id, TRUE
FROM books b
JOIN images i ON i.stored_name = 'cover-' || b.isbn || '.png'
ON CONFLICT DO NOTHING;

INSERT INTO users (full_name, email, password_hash, role) VALUES
    ('Mariana Solís', 'mariana.solis@libreriaonline.mx', '$2a$10$5mS9u0K1CdpizxQthvyF7O/MmY83UeO56dlwyAjaGPswKed5q309a', 'admin')
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (full_name, email, password_hash, role) VALUES
    ('Carlos Hernández', 'carlos.hernandez@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Ana Patricia Ruiz', 'ana.ruiz@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Luis Miguel Torres', 'luis.torres@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Sofía Navarro', 'sofia.navarro@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Diego Ramírez', 'diego.ramirez@yahoo.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Valeria Castro', 'valeria.castro@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Jorge Mendoza', 'jorge.mendoza@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Fernanda López', 'fernanda.lopez@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Ricardo Peña', 'ricardo.pena@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Camila Ortega', 'camila.ortega@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Andrés Ibarra', 'andres.ibarra@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Paola Jiménez', 'paola.jimenez@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Héctor Salazar', 'hector.salazar@yahoo.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Daniela Vega', 'daniela.vega@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Emilio Ríos', 'emilio.rios@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Regina Flores', 'regina.flores@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Santiago Morales', 'santiago.morales@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Renata Aguilar', 'renata.aguilar@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Iván Delgado', 'ivan.delgado@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Montserrat Reyes', 'montserrat.reyes@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Pablo Estrada', 'pablo.estrada@yahoo.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Alejandra Soto', 'alejandra.soto@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Mauricio Campos', 'mauricio.campos@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Ximena Barrera', 'ximena.barrera@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Óscar Núñez', 'oscar.nunez@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Isabela Paredes', 'isabela.paredes@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Rodrigo Fuentes', 'rodrigo.fuentes@outlook.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Lucía Méndez', 'lucia.mendez@gmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client'),
    ('Gabriel Ortiz', 'gabriel.ortiz@hotmail.com', '$2a$10$IaEvY3zUQtRh02xFX0q6t.EZ1hCLXhB/XjflX.s3tnprHKZyo9CRq', 'client')
ON CONFLICT (email) DO NOTHING;

COMMIT;
