"""
Seed the full CBSE Class 10 syllabus into Postgres.
Covers: Mathematics, Science, English, Hindi, Social Science, Sanskrit
Run once: python -m scripts.seed_syllabus
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models.db_models import Subject, Chapter, Topic

# ─── Structure: subject_name → [(chapter_name, [topic, ...]), ...] ────────────

FULL_SYLLABUS = {

    # ══════════════════════════════════════════════════════════════════════════
    # MATHEMATICS
    # ══════════════════════════════════════════════════════════════════════════
    "Mathematics": [
        ("Real Numbers", [
            "Euclid's Division Lemma",
            "Fundamental Theorem of Arithmetic",
            "Revisiting Irrational Numbers",
            "Revisiting Rational Numbers and their Decimal Expansions",
        ]),
        ("Polynomials", [
            "Geometrical Meaning of the Zeroes of a Polynomial",
            "Relationship between Zeroes and Coefficients of a Polynomial",
            "Division Algorithm for Polynomials",
        ]),
        ("Pair of Linear Equations in Two Variables", [
            "Graphical Method of Solution",
            "Algebraic Method - Substitution",
            "Algebraic Method - Elimination",
            "Algebraic Method - Cross-Multiplication",
            "Equations Reducible to a Pair of Linear Equations",
        ]),
        ("Quadratic Equations", [
            "Standard Form of a Quadratic Equation",
            "Solution by Factorisation",
            "Solution by Completing the Square",
            "Quadratic Formula",
            "Nature of Roots",
        ]),
        ("Arithmetic Progressions", [
            "nth Term of an AP",
            "Sum of First n Terms of an AP",
            "Application Problems on AP",
        ]),
        ("Triangles", [
            "Similar Figures",
            "Similarity of Triangles",
            "Criteria for Similarity of Triangles",
            "Areas of Similar Triangles",
            "Pythagoras Theorem",
        ]),
        ("Coordinate Geometry", [
            "Distance Formula",
            "Section Formula",
            "Area of a Triangle using Coordinates",
        ]),
        ("Introduction to Trigonometry", [
            "Trigonometric Ratios",
            "Trigonometric Ratios of Some Specific Angles",
            "Trigonometric Ratios of Complementary Angles",
            "Trigonometric Identities",
        ]),
        ("Some Applications of Trigonometry", [
            "Heights and Distances",
            "Application Problems - Angle of Elevation",
            "Application Problems - Angle of Depression",
        ]),
        ("Circles", [
            "Tangent to a Circle",
            "Number of Tangents from a Point on a Circle",
            "Length of a Tangent",
        ]),
        ("Areas Related to Circles", [
            "Perimeter and Area of a Circle - A Review",
            "Areas of Sector and Segment of a Circle",
            "Areas of Combinations of Plane Figures",
        ]),
        ("Surface Areas and Volumes", [
            "Surface Area of a Combination of Solids",
            "Volume of a Combination of Solids",
            "Conversion of Solid from One Shape to Another",
            "Frustum of a Cone",
        ]),
        ("Statistics", [
            "Mean of Grouped Data",
            "Mode of Grouped Data",
            "Median of Grouped Data",
            "Graphical Representation - Cumulative Frequency Ogive",
        ]),
        ("Probability", [
            "Probability - A Theoretical Approach",
            "Simple Problems on Single Events",
            "Problems on Two or More Events",
        ]),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # SCIENCE  (Chemistry + Biology + Physics chapters in NCERT order)
    # ══════════════════════════════════════════════════════════════════════════
    "Science": [
        # ── Chemistry ────────────────────────────────────────────────────────
        ("Chemical Reactions and Equations", [
            "Chemical Equations",
            "Types of Chemical Reactions - Combination",
            "Types of Chemical Reactions - Decomposition",
            "Types of Chemical Reactions - Displacement and Double Displacement",
            "Oxidation and Reduction Reactions",
            "Effects of Oxidation in Everyday Life",
        ]),
        ("Acids, Bases and Salts", [
            "Understanding Acids and Bases",
            "Reactions of Acids and Bases",
            "What do Acids and Bases have in Common",
            "Strength of Acid or Base - pH Scale",
            "Importance of pH in Everyday Life",
            "Salts - Preparation and Properties",
            "Bleaching Powder, Baking Soda, Washing Soda, Plaster of Paris",
        ]),
        ("Metals and Non-metals", [
            "Physical Properties of Metals and Non-metals",
            "Chemical Properties of Metals",
            "How do Metals and Non-metals React",
            "Occurrence of Metals - Activity Series",
            "Extraction of Metals",
            "Refining of Metals",
            "Corrosion and its Prevention",
            "Alloys",
        ]),
        ("Carbon and its Compounds", [
            "Bonding in Carbon",
            "Versatile Nature of Carbon",
            "Homologous Series",
            "Nomenclature of Carbon Compounds",
            "Chemical Properties of Carbon Compounds",
            "Important Carbon Compounds - Ethanol and Ethanoic Acid",
            "Soaps and Detergents",
        ]),
        ("Periodic Classification of Elements", [
            "Early Attempts at Classification - Dobereiner and Newlands",
            "Mendeleev's Periodic Table",
            "Modern Periodic Table",
            "Trends in the Modern Periodic Table",
        ]),
        # ── Biology ──────────────────────────────────────────────────────────
        ("Life Processes", [
            "What are Life Processes",
            "Nutrition - Autotrophic and Heterotrophic",
            "Respiration",
            "Transportation in Plants and Animals",
            "Excretion in Plants and Animals",
        ]),
        ("Control and Coordination", [
            "Animals - Nervous System",
            "Coordination in Plants - Tropic Movements",
            "Chemical Coordination in Animals - Hormones",
        ]),
        ("How do Organisms Reproduce", [
            "Asexual Reproduction",
            "Sexual Reproduction in Flowering Plants",
            "Reproduction in Human Beings",
            "Reproductive Health",
        ]),
        ("Heredity and Evolution", [
            "Accumulation of Variation during Reproduction",
            "Heredity - Mendel's Experiments",
            "How do these Traits get Expressed",
            "Sex Determination",
            "Evolution",
            "Speciation",
            "Evolution and Classification",
            "Evolution by Stages",
        ]),
        ("Our Environment", [
            "Ecosystem - What are its Components",
            "Food Chains and Webs",
            "How do our Activities Affect the Environment",
            "Ozone Layer and its Depletion",
            "Managing the Garbage we Produce",
        ]),
        ("Management of Natural Resources", [
            "Why do we Need to Manage our Resources",
            "Forests and Wildlife - Stakeholders",
            "Water for All",
            "Coal and Petroleum",
            "Sustainable Management of Natural Resources",
        ]),
        # ── Physics ──────────────────────────────────────────────────────────
        ("Light - Reflection and Refraction", [
            "Reflection of Light",
            "Spherical Mirrors",
            "Image Formation by Spherical Mirrors",
            "Mirror Formula and Magnification",
            "Refraction of Light",
            "Refraction through a Glass Slab",
            "Spherical Lenses",
            "Image Formation by Lenses",
            "Lens Formula and Magnification",
            "Power of a Lens",
        ]),
        ("Human Eye and Colourful World", [
            "Human Eye",
            "Defects of Vision and their Correction",
            "Refraction of Light through a Prism",
            "Dispersion of Light",
            "Atmospheric Refraction",
            "Scattering of Light - Tyndall Effect",
        ]),
        ("Electricity", [
            "Electric Current and Circuit",
            "Electric Potential and Potential Difference",
            "Ohm's Law",
            "Resistance of a Conductor",
            "Factors Affecting Resistance",
            "Resistors in Series",
            "Resistors in Parallel",
            "Heating Effect of Electric Current",
            "Electric Power",
        ]),
        ("Magnetic Effects of Electric Current", [
            "Magnetic Field and Field Lines",
            "Magnetic Field due to a Current-Carrying Conductor",
            "Force on a Current-Carrying Conductor in a Magnetic Field",
            "Electric Motor",
            "Electromagnetic Induction",
            "Electric Generator",
            "Domestic Electric Circuits",
        ]),
        ("Sources of Energy", [
            "What is a Good Source of Energy",
            "Conventional Sources of Energy",
            "Alternative Sources of Energy - Solar, Wind, Hydro",
            "Alternative Sources of Energy - Biomass, Geothermal, Tidal, Nuclear",
            "Environmental Consequences",
        ]),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # ENGLISH
    # ══════════════════════════════════════════════════════════════════════════
    "English": [
        ("First Flight - Prose", [
            "A Letter to God",
            "Nelson Mandela: Long Walk to Freedom",
            "Two Stories about Flying (His First Flight + Black Aeroplane)",
            "From the Diary of Anne Frank",
            "Glimpses of India",
            "Mijbil the Otter",
            "Madam Rides the Bus",
            "The Sermon at Benares",
            "The Proposal (Play)",
        ]),
        ("First Flight - Poetry", [
            "Dust of Snow",
            "Fire and Ice",
            "A Tiger in the Zoo",
            "How to Tell Wild Animals",
            "The Ball Poem",
            "Amanda!",
            "Animals",
            "The Trees",
            "Fog",
            "The Tale of Custard the Dragon",
            "For Anne Gregory",
        ]),
        ("Footprints Without Feet", [
            "A Triumph of Surgery",
            "The Thief's Story",
            "The Midnight Visitor",
            "A Question of Trust",
            "Footprints Without Feet",
            "The Making of a Scientist",
            "The Necklace",
            "The Hack Driver",
            "Bholi",
            "The Book That Saved the Earth",
        ]),
        ("Grammar and Writing Skills", [
            "Tenses and Verb Forms",
            "Modals",
            "Subject-Verb Agreement",
            "Reported Speech (Direct and Indirect)",
            "Active and Passive Voice",
            "Clauses (Noun, Adjective, Adverb)",
            "Formal Letter Writing",
            "Informal Letter Writing",
            "Article and Notice Writing",
            "Paragraph and Story Writing",
        ]),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # HINDI
    # ══════════════════════════════════════════════════════════════════════════
    "Hindi": [
        ("Kshitij Bhag 2 - Kavya Khand", [
            "Sakhiyan avn Sabad - Kabir",
            "Ram-Lakshman-Parasuram Samvad - Tulasidas",
            "Savaiya aur Kavitt - Dev",
            "Aatmakathya - Jayashankar Prasad",
            "Utsaah aur Att Nahi Rahi - Suryakant Tripathi Nirala",
            "Yeh Danturit Muskan aur Fasal - Nagarjuna",
            "Chhaya Mat Chhuona - Girija Kumar Mathur",
            "Kanyadan - Rituraj",
            "Sangatkar - Manglesh Dabral",
        ]),
        ("Kshitij Bhag 2 - Gadya Khand", [
            "Netaji ka Chasma - Swayam Prakash",
            "Balgobin Bhagat - Rambriksh Benipuri",
            "Lakhnawi Andaj - Yashpal",
            "Manviya Karuna ki Divya Chamak - Sarveshwar Dayal Saxena",
            "Ek Kahani Yeh Bhi - Mannu Bhandari",
            "Striya Shiksha ke Virodhi Kutarkon ka Khandan - Mahavir Prasad Dwivedi",
            "Naukush ka Beta - Premchand",
            "Sanskriti - Bhadoravi",
        ]),
        ("Kritika Bhag 2", [
            "Mata ka Anchal - Shivpujan Sahay",
            "George Pancham ki Naak - Kamleshwar",
            "Sana-Sana Hath Jodi - Madhu Kankria",
            "Ehi Thaiyan Jhulni Herani Ho Rama - Shivamaur Mishra",
            "Main Kyun Likhta Hoon - Nirmal Verma",
        ]),
        ("Sparsh Bhag 2 - Gadya", [
            "Bade Bhai Sahab - Premchand",
            "Diary ka Ek Panna - Siteswar Prasad",
            "Tantara Vamiro Katha - Leeladhar Mandloi",
            "Teesri Kasam ke Shilpkar Shailendra - Prahlad Agarwal",
            "Girgit - Anton Chekhov",
            "Aab Kahan Doosre ke Dukh se Dukhi Honewale - Nida Fazli",
            "Patjhar mein Tooti Pattiyaan - Ratan Singh",
            "Kartoos - Habib Tanvir",
        ]),
        ("Sparsh Bhag 2 - Kavya", [
            "Kabir ki Sakhiyan",
            "Meera ke Pad",
            "Bihari ke Dohe",
            "Manushyata - Maithilisharan Gupt",
            "Parvat Pradesh mein Pavas - Sumitranandan Pant",
            "Madhur Madhur Mere Deepak Jal - Mahadevi Verma",
            "Top - Kedarnath Agarwal",
            "Yeh Daanturit Muskan - Nagarjuna",
            "Tataara-Vamiro Katha (poem adaptation)",
            "Oor ki Soyi Meri Lori - Sarveshwar Dayal Saxena",
        ]),
        ("Sanchayan Bhag 2", [
            "Harihar Kaka - Mithileshwar",
            "Sapnon ke-se Din - Gurdial Singh",
            "Topi Shukla - Rahi Masoom Reza",
        ]),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # SOCIAL SCIENCE
    # ══════════════════════════════════════════════════════════════════════════
    "Social Science": [
        ("History - India and the Contemporary World II", [
            "The Rise of Nationalism in Europe",
            "Nationalism in India",
            "The Making of a Global World",
            "The Age of Industrialisation",
            "Print Culture and the Modern World",
        ]),
        ("Geography - Contemporary India II", [
            "Resources and Development",
            "Forest and Wildlife Resources",
            "Water Resources",
            "Agriculture",
            "Minerals and Energy Resources",
            "Manufacturing Industries",
            "Lifelines of National Economy",
        ]),
        ("Civics - Democratic Politics II", [
            "Power Sharing",
            "Federalism",
            "Democracy and Diversity",
            "Gender, Religion and Caste",
            "Popular Struggles and Movements",
            "Political Parties",
            "Outcomes of Democracy",
            "Challenges to Democracy",
        ]),
        ("Economics - Understanding Economic Development", [
            "Development",
            "Sectors of the Indian Economy",
            "Money and Credit",
            "Globalisation and the Indian Economy",
            "Consumer Rights",
        ]),
    ],

    # ══════════════════════════════════════════════════════════════════════════
    # SANSKRIT (Optional)
    # ══════════════════════════════════════════════════════════════════════════
    "Sanskrit": [
        ("Shemushi Bhag 2", [
            "Shuchiparyavaranam",
            "Budhhibalavati Bhavati",
            "Vyayamah Sarvada Pathyah",
            "Shaashvati Aasha",
            "Jnanasya Rahasyam",
            "Suktimaauktikam",
            "Saptabhinaanaam Samarthyam",
            "Kavitasaurabham",
            "Sukhadukhayoh Vishleshan",
            "Bhoomi Suktam",
            "Praninamupakarak scha",
        ]),
        ("Vyakaranavithy", [
            "Sandhi - Swar Sandhi",
            "Sandhi - Vyanjan Sandhi",
            "Sandhi - Visarg Sandhi",
            "Samas - Types and Examples",
            "Karak and Vibhakti",
            "Pratyay - Krit and Taddhit",
            "Vachya - Kartri, Karma, Bhav",
            "Alankar - Upama, Rupak, Anupras",
            "Anuvaad - Translation Practice",
        ]),
        ("Abhyaswaan Bhav", [
            "Apathit Gadyansh (Unseen Passage - Prose)",
            "Apathit Padyansh (Unseen Passage - Poetry)",
            "Rachnatmak Lekhan - Patra",
            "Rachnatmak Lekhan - Anuched",
            "Rachnatmak Lekhan - Chitra Varnan",
            "Grammar Application Practice",
        ]),
    ],
}


def seed():
    init_db()
    db = SessionLocal()
    total_subjects = 0
    total_chapters = 0
    total_topics = 0

    try:
        for subject_name, chapters in FULL_SYLLABUS.items():
            subject = db.query(Subject).filter(Subject.name == subject_name).first()
            if not subject:
                subject = Subject(name=subject_name)
                db.add(subject)
                db.commit()
                db.refresh(subject)
                total_subjects += 1
                print(f"\n✅ Subject: {subject_name} (id={subject.id})")
            else:
                print(f"\nℹ️  Subject already exists: {subject_name} (id={subject.id})")

            for ch_num, (chapter_name, topics) in enumerate(chapters, start=1):
                chapter = db.query(Chapter).filter(
                    Chapter.subject_id == subject.id,
                    Chapter.name == chapter_name,
                ).first()
                if not chapter:
                    chapter = Chapter(
                        subject_id=subject.id,
                        name=chapter_name,
                        number=ch_num,
                    )
                    db.add(chapter)
                    db.commit()
                    db.refresh(chapter)
                    total_chapters += 1
                    print(f"  📖 Chapter {ch_num}: {chapter_name}")

                new_topics = 0
                for topic_name in topics:
                    exists = db.query(Topic).filter(
                        Topic.chapter_id == chapter.id,
                        Topic.name == topic_name,
                    ).first()
                    if not exists:
                        db.add(Topic(chapter_id=chapter.id, name=topic_name))
                        new_topics += 1
                        total_topics += 1
                db.commit()
                if new_topics:
                    print(f"     └─ {new_topics} topics added")

        print(f"\n{'='*60}")
        print(f"✅ Seeding complete!")
        print(f"   Subjects  : {total_subjects} new")
        print(f"   Chapters  : {total_chapters} new")
        print(f"   Topics    : {total_topics} new")

        # Final DB counts
        s = db.query(Subject).count()
        c = db.query(Chapter).count()
        t = db.query(Topic).count()
        print(f"\n   DB totals → {s} subjects | {c} chapters | {t} topics")
        print(f"{'='*60}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
