-- Seed the taxonomy. 11 top-level classes + representative subclasses.
-- Subclass rows reference the top-level via parent_class_id.

INSERT INTO taxonomy_classes (slug, name, level, description, canonical_materials, search_keywords, extension_table) VALUES
('electronic_eap',  'Electronic EAPs',                 1, 'Electroactive polymers driven by electric field (Maxwell stress, electrostriction, ferroelectric dipole alignment).', ARRAY['VHB 4910','PVDF-TrFE','silicone'], ARRAY['dielectric elastomer actuator','DEA','HASEL','electroactive polymer','Maxwell stress','ferroelectric polymer'], 'materials_polymer'),
('ionic_eap',       'Ionic EAPs',                      1, 'Electroactive polymers driven by ion migration; low voltage, typically bending actuators.', ARRAY['Nafion-Pt','polypyrrole','polyaniline'], ARRAY['ionic polymer metal composite','IPMC','conducting polymer actuator','polypyrrole actuator','Nafion'], 'materials_polymer'),
('thermal_polymer', 'Thermally driven polymers',       1, 'Liquid crystal elastomers, shape memory polymers, twisted/coiled polymer muscles.', ARRAY['RM257-LCE','coiled nylon','coiled polyethylene'], ARRAY['liquid crystal elastomer','LCE','shape memory polymer','twisted coiled polymer','TCPA','nylon muscle','fishing line muscle'], 'materials_polymer'),
('gel',             'Stimuli-responsive gels',         1, 'Hydrogels responding to pH, temperature, light, humidity.', ARRAY['PNIPAM','azobenzene hydrogel'], ARRAY['PNIPAM','responsive hydrogel','pH responsive gel','humidity actuator','azobenzene hydrogel'], 'materials_polymer'),
('sma',             'Shape memory alloys',             1, 'Metallic alloys with reversible martensite-austenite phase transformation.', ARRAY['Nitinol','CuAlNi','Ni-Mn-Ga'], ARRAY['Nitinol','shape memory alloy','SMA actuator','CuAlNi','ferromagnetic shape memory','Ni-Mn-Ga'], 'materials_sma'),
('piezo',           'Piezoelectric / ferroelectric ceramics', 1, 'Ceramics producing strain under electric field via piezoelectric / ferroelectric coupling.', ARRAY['PZT','PMN-PT','BaTiO3'], ARRAY['PZT','piezoelectric actuator','PMN-PT','single crystal piezo','ferroelectric ceramic'], 'materials_piezo'),
('carbon',          'Carbon-based',                    1, 'Carbon nanotube yarns, graphene, rGO actuators.', ARRAY['MWCNT yarn','rGO film'], ARRAY['carbon nanotube yarn','CNT muscle','graphene actuator','rGO actuator','Baughman torsional actuator'], 'materials_cnt'),
('biohybrid',       'Biohybrid',                       1, 'Living cells on engineered scaffolds acting as actuators.', ARRAY['cardiomyocyte on PDMS','C2C12 skeletal'], ARRAY['biohybrid actuator','cardiomyocyte actuator','skeletal muscle robot','optogenetic muscle','bio-bot'], 'materials_biohybrid'),
('pneumatic',       'Pneumatic / fluidic',             1, 'Gas- or fluid-driven soft actuators: McKibben muscles, HASELs, PneuNets, bellows.', ARRAY['McKibben muscle','HASEL actuator','PneuNet'], ARRAY['McKibben muscle','pneumatic artificial muscle','soft pneumatic actuator','HASEL','fiber reinforced elastomer'], 'materials_pneumatic'),
('magnetic',        'Magnetic / magnetoactive',        1, 'Elastomers with magnetic fillers responding to external fields.', ARRAY['NdFeB-silicone','Fe3O4-PDMS'], ARRAY['magnetorheological elastomer','MR elastomer','magnetic soft actuator','NdFeB composite','magnetoactive elastomer'], 'materials_magnetic'),
('combustion',      'Combustion / chemomechanical',    1, 'Chemical reaction-driven actuation (combustion, decomposition).', ARRAY['guncotton actuator'], ARRAY['combustion actuator','chemomechanical actuator','explosive actuator'], NULL);

-- Subclasses for Electronic EAPs
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='electronic_eap'), 'dea',                'Dielectric elastomer actuator',         2, 'Elastomer sandwiched between compliant electrodes; area expands under field (Maxwell stress).', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='electronic_eap'), 'ferroelectric_polymer', 'Ferroelectric polymer',             2, 'PVDF / P(VDF-TrFE) exhibiting ferroelectric switching.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='electronic_eap'), 'electrostrictive_polymer', 'Electrostrictive polymer',       2, 'Strain quadratic in applied field.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='electronic_eap'), 'hasel',              'HASEL actuator',                        2, 'Hydraulically-amplified self-healing electrostatic; hybrid fluidic + electric.', 'materials_polymer');

-- Subclasses for Ionic EAPs
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='ionic_eap'), 'ipmc',              'Ionic polymer-metal composite', 2, 'Nafion or similar with electroplated metal electrodes; bends under low voltage.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='ionic_eap'), 'conducting_polymer','Conducting polymer actuator',   2, 'Polypyrrole, polyaniline, PEDOT driven by redox ion insertion.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='ionic_eap'), 'ionic_gel',         'Ionic gel actuator',            2, 'Gel containing mobile ions.', 'materials_polymer');

-- Subclasses for thermally driven polymers
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='thermal_polymer'), 'lce',  'Liquid crystal elastomer', 2, 'Crosslinked polymer with aligned mesogens; reversible contraction at nematic-isotropic transition.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='thermal_polymer'), 'smp',  'Shape memory polymer',     2, 'Programmed shape recovered on heating above switching temperature.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='thermal_polymer'), 'tcpa', 'Twisted/coiled polymer actuator', 2, 'Thermally-actuated twisted and coiled polymer fibers (nylon, polyethylene).', 'materials_polymer');

-- Subclasses for gels
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='gel'), 'pnipam',           'PNIPAM hydrogel',      2, 'Thermoresponsive poly(N-isopropylacrylamide) gel.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='gel'), 'ph_gel',           'pH-responsive gel',    2, '', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='gel'), 'azobenzene_gel',   'Light-responsive gel', 2, 'Azobenzene-functionalized hydrogel actuating under UV/visible light.', 'materials_polymer'),
((SELECT class_id FROM taxonomy_classes WHERE slug='gel'), 'humidity_gel',     'Humidity-responsive gel', 2, '', 'materials_polymer');

-- Subclasses for SMA
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='sma'), 'niti',    'NiTi (Nitinol)',   2, 'Binary Ni-Ti alloy, dominant commercial SMA.', 'materials_sma'),
((SELECT class_id FROM taxonomy_classes WHERE slug='sma'), 'cualni',  'CuAlNi',           2, 'Copper-aluminium-nickel SMA.', 'materials_sma'),
((SELECT class_id FROM taxonomy_classes WHERE slug='sma'), 'fsma',    'Ferromagnetic SMA',2, 'Ni-Mn-Ga and related; magnetic-field actuation.', 'materials_sma');

-- Subclasses for piezo
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='piezo'), 'pzt',       'PZT',               2, 'Lead zirconate titanate, dominant piezo ceramic.', 'materials_piezo'),
((SELECT class_id FROM taxonomy_classes WHERE slug='piezo'), 'pmn_pt',    'PMN-PT',            2, 'Lead magnesium niobate-lead titanate single-crystal.', 'materials_piezo'),
((SELECT class_id FROM taxonomy_classes WHERE slug='piezo'), 'piezo_polymer', 'Piezo polymer', 2, 'PVDF-based piezoelectric polymers.', 'materials_piezo');

-- Subclasses for carbon
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='carbon'), 'cnt_yarn',    'CNT yarn muscle',  2, 'Twisted/coiled carbon nanotube yarn, thermal or electrochemical actuation.', 'materials_cnt'),
((SELECT class_id FROM taxonomy_classes WHERE slug='carbon'), 'graphene',    'Graphene actuator',2, 'Graphene or rGO films / composites.', 'materials_cnt');

-- Subclasses for biohybrid
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='biohybrid'), 'cardiac_biohybrid',  'Cardiac cell-based', 2, 'Cardiomyocytes on engineered scaffold; self-actuating.', 'materials_biohybrid'),
((SELECT class_id FROM taxonomy_classes WHERE slug='biohybrid'), 'skeletal_biohybrid', 'Skeletal cell-based', 2, 'C2C12 / primary skeletal muscle cells on scaffold.', 'materials_biohybrid'),
((SELECT class_id FROM taxonomy_classes WHERE slug='biohybrid'), 'optogenetic_biohybrid', 'Optogenetic biohybrid', 2, 'Light-controlled via channelrhodopsin.', 'materials_biohybrid');

-- Subclasses for pneumatic
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='pneumatic'), 'mckibben',   'McKibben muscle',              2, 'Braided-sleeve pneumatic artificial muscle.', 'materials_pneumatic'),
((SELECT class_id FROM taxonomy_classes WHERE slug='pneumatic'), 'pneunet',    'PneuNet / soft pneumatic',     2, 'Chamber-network soft pneumatic actuator.', 'materials_pneumatic'),
((SELECT class_id FROM taxonomy_classes WHERE slug='pneumatic'), 'fre',        'Fiber-reinforced elastomer',   2, 'Elastomer with embedded fibers for directional contraction.', 'materials_pneumatic');

-- Subclasses for magnetic
INSERT INTO taxonomy_classes (parent_class_id, slug, name, level, description, extension_table) VALUES
((SELECT class_id FROM taxonomy_classes WHERE slug='magnetic'), 'mr_elastomer',     'Magnetorheological elastomer', 2, '', 'materials_magnetic'),
((SELECT class_id FROM taxonomy_classes WHERE slug='magnetic'), 'hard_magnetic_soft', 'Hard-magnetic soft actuator', 2, 'NdFeB-filled elastomer with programmed magnetization.', 'materials_magnetic');
