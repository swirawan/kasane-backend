(() => {
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduceMotion = motionQuery.matches;
  const body = document.body;
  const nav = document.getElementById('siteNav');
  const menuToggle = document.getElementById('menuToggle');
  const mobileMenu = document.getElementById('mobileMenu');

  const idTranslations = {
  "Services": "Layanan",
  "01 / WHAT WE DO": "01 / APA YANG KAMI KERJAKAN",
  "02 / WAYS TO WORK WITH US": "02 / CARA BEKERJA DENGAN KAMI",
  "KASANE MUSUBI™ / 結び · PERSONAL DIGITAL INVITATIONS": "KASANE MUSUBI™ / 結び · UNDANGAN DIGITAL PERSONAL",
  "MUSUBI™": "MUSUBI™",
  "By preparing a brief, you agree KASANE may contact you about this event.": "Dengan menyiapkan brief, Anda menyetujui KASANE menghubungi Anda mengenai event ini.",
  "Required field.": "Kolom ini wajib diisi.",
  "Please enter a valid email address.": "Masukkan alamat email yang valid.",
  "Please enter a phone number for this contact method.": "Masukkan nomor telepon untuk cara kontak ini.",
  "Please select an event type.": "Pilih jenis event.",
  "Please tell us a little about the event.": "Ceritakan sedikit tentang event Anda.",
  "Sending your brief…": "Mengirim brief Anda…",
  "Brief received.": "Brief diterima.",
  "We’ll contact you through your preferred channel.": "Kami akan menghubungi Anda melalui cara kontak pilihan Anda.",
  "We could not send the brief online. Opening your email instead.": "Brief belum dapat dikirim online. Kami membuka email Anda sebagai alternatif.",
  "Add MUSUBI™ to my brief": "Tambahkan MUSUBI™ ke brief saya",
  "Product added to brief": "Produk ditambahkan ke brief",
  "Remove selected product": "Hapus produk terpilih",
  "Preferred contact": "Cara kontak pilihan",
  "Email": "Email",
  "Call": "Telepon",
  "SMS": "SMS",
  "04 / WHY KASANE": "04 / MENGAPA KASANE",
  "05 / THE KASANE BOARD": "05 / KASANE EVENT BOARD",
  "06 / CREATIVE DIRECTION": "06 / ARAH KREATIF",
  "07 / HOW WE WORK": "07 / CARA KAMI BEKERJA",
  "08 / ABOUT KASANE": "08 / TENTANG KASANE",
  "09 / BEFORE WE BEGIN": "09 / SEBELUM KITA MULAI",
  "10 / START A BRIEF": "10 / MULAI BRIEF",
  "Packages": "Paket",
  "Direction": "Arah Kreatif",
  "About": "Tentang",
  "Start a brief": "Mulai brief",
  "Start an event brief": "Mulai brief acara",
  "EVENTS · EXPERIENCES · PRODUCTION": "EVENT · EXPERIENCE · PRODUKSI",
  "Layered moments.": "Momen yang berlapis.",
  "Beautifully produced.": "Diproduksi dengan indah.",
  "We organize celebrations with a calm head, a sharp eye, and a production plan strong enough to let the moment feel effortless.": "Kami merancang dan menjalankan perayaan dengan kepala dingin, mata yang tajam, dan rencana produksi yang kuat—agar setiap momen terasa mengalir tanpa beban.",
  "Plan with KASANE": "Rencanakan bersama KASANE",
  "See our direction": "Lihat arah kreatif kami",
  "Based in": "Berbasis di",
  "Focused on": "Fokus pada",
  "Built around": "Dibangun melalui",
  "Wedding · Sweet Seventeen · Private & Brand Events": "Wedding · Sweet Seventeen · Private & Brand Event",
  "Planning · Creative Direction · Production": "Planning · Arah Kreatif · Produksi",
  "WEDDING": "PERNIKAHAN",
  "PRIVATE": "PRIVAT",
  "WEDDINGS": "WEDDING",
  "SWEET SEVENTEENS": "SWEET SEVENTEEN",
  "PRIVATE CELEBRATIONS": "ACARA PRIVAT",
  "CORPORATE EVENTS": "ACARA KORPORAT",
  "BRAND EXPERIENCES": "BRAND EXPERIENCE",
  "PRODUCTION": "PRODUKSI",
  "One collective.": "Satu kolektif.",
  "Every moving part.": "Setiap detail terhubung.",
  "From the first brief to final cue, KASANE can lead the full event or join the parts where you need structure, taste, and production control.": "Dari brief pertama hingga cue terakhir, KASANE dapat memimpin seluruh acara atau masuk pada bagian yang membutuhkan struktur, taste, dan kontrol produksi.",
  "Wedding Organization": "Wedding Organizer",
  "Full planning · coordination · guest flow": "Full planning · koordinasi · alur tamu",
  "Concept · styling · show flow · celebration": "Konsep · styling · alur acara · perayaan",
  "Private Celebrations": "Acara Privat",
  "Birthdays · anniversaries · intimate occasions": "Ulang tahun · anniversary · acara intim",
  "Brand & Corporate": "Brand & Korporat",
  "Launches · dinners · gatherings · activations": "Launch · dinner · gathering · activation",
  "Event Production": "Produksi Event",
  "Stage · technical · vendor · run of show": "Stage · teknis · vendor · run of show",
  "Choose the layer.": "Pilih lapisannya.",
  "Or choose everything.": "Atau serahkan semuanya.",
  "Choose a focused scope or hand us the whole event. KASANE can source the venue and vendors, shape the creative direction, control the timeline, and keep every moving part connected from the first brief to the final cue.": "Pilih scope tertentu atau serahkan seluruh acara kepada kami. KASANE dapat mencarikan venue dan vendor, membentuk arah kreatif, mengendalikan timeline, dan memastikan semua bagian tetap terhubung dari brief pertama hingga cue terakhir.",
  "01 / COMPLETE": "01 / LENGKAP",
  "Most complete": "Paling lengkap",
  "The whole package. One KASANE team across planning, creative direction, vendor sourcing, production and event-day execution—built so your event feels seamless.": "Paket lengkap. Satu tim KASANE untuk planning, arah kreatif, pencarian vendor, produksi, dan eksekusi hari-H—dirancang agar acara Anda terasa seamless.",
  "Event strategy & master planning": "Strategi acara & master planning",
  "Hotel / venue sourcing & coordination": "Pencarian & koordinasi hotel / venue",
  "Catering, décor & styling partners": "Catering, dekorasi & partner styling",
  "Photo / videography, band & entertainment": "Foto / videografi, band & entertainment",
  "Budget, timeline & guest-flow control": "Kontrol budget, timeline & alur tamu",
  "Production, rehearsal & run of show": "Produksi, rehearsal & run of show",
  "Full on-site event-day team": "Tim lengkap on-site di hari-H",
  "Choose Full KASANE": "Pilih Full KASANE",
  "02 / PLAN": "02 / PLANNING",
  "Planning-led": "Fokus planning",
  "Plan + Coordinate": "Planning + Koordinasi",
  "For clients who already have parts of the vision, but need structure, vendor control, timeline ownership and a calm event day.": "Untuk klien yang sudah memiliki sebagian visi, tetapi membutuhkan struktur, kontrol vendor, kepemilikan timeline, dan hari-H yang tetap tenang.",
  "Planning architecture": "Struktur planning",
  "Vendor & venue coordination": "Koordinasi vendor & venue",
  "Timeline & guest journey": "Timeline & perjalanan tamu",
  "Rehearsal & event-day coordination": "Rehearsal & koordinasi hari-H",
  "Choose this scope": "Pilih scope ini",
  "03 / PRODUCE": "03 / PRODUKSI",
  "Production-led": "Fokus produksi",
  "Produce the Show": "Produksi Acaranya",
  "For a concept that already exists and needs disciplined technical delivery, vendor integration, cueing and on-site production control.": "Untuk konsep yang sudah ada dan membutuhkan eksekusi teknis yang disiplin, integrasi vendor, cueing, dan kontrol produksi on-site.",
  "Technical production planning": "Planning produksi teknis",
  "Stage, sound, lighting & screens": "Stage, sound, lighting & screen",
  "Vendor technical handoff": "Handoff teknis antar-vendor",
  "Rehearsal, cues & run of show": "Rehearsal, cue & run of show",
  "Hotel & Venue": "Hotel & Venue",
  "Catering": "Catering",
  "Décor": "Dekorasi",
  "Photo & Video": "Foto & Video",
  "Band & Entertainment": "Band & Entertainment",
  "MC & Talent": "MC & Talent",
  "Technical Production": "Produksi Teknis",
  "What are we": "Apa yang sedang",
  "building?": "kita bangun?",
  "KASANE / EVENT BOARD": "KASANE / EVENT BOARD",
  "LIVE BRIEF": "BRIEF AKTIF",
  "EVENT": "ACARA",
  "SCALE": "SKALA",
  "FOCUS": "FOKUS",
  "STATUS": "STATUS",
  "OPEN FOR BRIEFS": "MENERIMA BRIEF",
  "EAST JAVA / ID": "JAWA TIMUR / ID",
  "Pause": "Jeda",
  "Play": "Putar",
  "Sound": "Suara",
  "Previous event": "Acara sebelumnya",
  "Next event": "Acara berikutnya",
  "Designed to feel": "Dirancang agar terasa",
  "like you.": "seperti Anda.",
  "These are the worlds KASANE is built to shape—not fixed packages, but starting points for your own event language.": "Ini adalah dunia visual yang dapat KASANE bentuk—bukan paket tetap, melainkan titik awal untuk bahasa acara Anda sendiri.",
  "01 / WEDDING": "01 / WEDDING",
  "02 / CELEBRATION": "02 / PERAYAAN",
  "03 / PRODUCTION": "03 / PRODUKSI",
  "04 / PRIVATE": "04 / PRIVAT",
  "Warm light · tactile tablescape · precision without stiffness": "Cahaya hangat · tablescape bertekstur · presisi tanpa terasa kaku",
  "View concept ↗": "Lihat konsep ↗",
  "Atmosphere · music · movement": "Atmosfer · musik · gerak",
  "Cues · lighting · stage · technical flow": "Cue · lighting · stage · alur teknis",
  "Intimate guest list · meaningful details · lingering dinner": "Tamu intim · detail bermakna · dinner yang panjang",
  "Calm before": "Tenang sebelum",
  "the curtain rises.": "acara dimulai.",
  "Listen": "Dengarkan",
  "We define the people, purpose, budget, visual language, non-negotiables, and what you never want the day to feel like.": "Kami memahami orang-orangnya, tujuan, budget, bahasa visual, hal yang tidak bisa ditawar, dan bagaimana Anda tidak ingin hari itu terasa.",
  "Layer": "Susun",
  "Venue, vendors, styling, production, timeline, guest journey and details are built into one working event system.": "Venue, vendor, styling, produksi, timeline, perjalanan tamu, dan detail disusun menjadi satu sistem acara yang bekerja bersama.",
  "Produce": "Produksi",
  "We coordinate decisions, rehearsals, technical needs, vendor movement and the run of show with clear ownership.": "Kami mengoordinasikan keputusan, rehearsal, kebutuhan teknis, pergerakan vendor, dan run of show dengan ownership yang jelas.",
  "Be Present": "Nikmati Momennya",
  "On event day, KASANE holds the moving parts so you can actually experience what you created.": "Di hari-H, KASANE memegang semua bagian yang bergerak agar Anda benar-benar dapat menikmati acara yang telah Anda ciptakan.",
  "Structure with taste.": "Struktur dengan taste.",
  "Production with feeling.": "Produksi dengan rasa.",
  "KASANE COLLECTIVE is an event organizer and production studio serving Malang, Surabaya, and projects across East Java. We are building a modern alternative to the “package-first” event model: thoughtful planning, strong creative direction, transparent coordination and a day that still feels human.": "KASANE COLLECTIVE adalah event organizer dan production studio untuk Malang, Surabaya, dan proyek di Jawa Timur. Kami membangun alternatif modern dari model event yang serba paket: planning yang matang, arah kreatif yang kuat, koordinasi yang transparan, dan hari-H yang tetap terasa personal.",
  "Intentional": "Penuh niat",
  "Calm": "Tenang",
  "Detailed": "Detail",
  "Collaborative": "Kolaboratif",
  "A few useful": "Beberapa jawaban",
  "answers.": "yang berguna.",
  "Do you only handle weddings?": "Apakah KASANE hanya menangani wedding?",
  "No. Weddings are a core focus, alongside Sweet Seventeen celebrations, private occasions, corporate events, brand experiences and production support.": "Tidak. Wedding adalah salah satu fokus utama kami, bersama Sweet Seventeen, acara privat, event korporat, brand experience, dan dukungan produksi.",
  "Can KASANE handle only coordination or production?": "Apakah KASANE bisa menangani koordinasi atau produksi saja?",
  "Yes. The scope can be full-service or focused. We can lead the full event, step in for coordination, or handle selected production components depending on the brief.": "Bisa. Scope dapat full-service atau fokus pada bagian tertentu. Kami dapat memimpin seluruh event, masuk untuk koordinasi, atau menangani komponen produksi tertentu sesuai brief.",
  "Where do you work?": "Area mana yang KASANE layani?",
  "Our home base is Malang and Surabaya, with East Java projects considered based on venue, scale and production requirements.": "Home base kami adalah Malang dan Surabaya, dengan proyek di Jawa Timur dipertimbangkan berdasarkan venue, skala, dan kebutuhan produksi.",
  "How early should we start?": "Seberapa awal sebaiknya kita mulai?",
  "The earlier we join, the more we can shape the event strategically. For near-term dates, send the brief anyway—we will tell you quickly what is realistic.": "Semakin awal kami bergabung, semakin banyak yang dapat kami bentuk secara strategis. Untuk tanggal yang sudah dekat, tetap kirim brief—kami akan memberi tahu dengan cepat apa yang realistis.",
  "Tell us what": "Ceritakan apa yang",
  "you’re imagining.": "Anda bayangkan.",
  "You do not need a finished concept. A date, city, guest count and the feeling you want are enough to start.": "Anda tidak perlu memiliki konsep yang sudah jadi. Tanggal, kota, jumlah tamu, dan suasana yang Anda inginkan sudah cukup untuk memulai.",
  "Events · Experiences · Production": "Event · Experience · Produksi",
  "Name *": "Nama *",
  "Event type *": "Jenis event *",
  "Select event": "Pilih event",
  "Wedding": "Wedding",
  "Planning · coordination · guest flow": "Planning · koordinasi · alur tamu",
  "Concept · styling · show flow": "Konsep · styling · alur acara",
  "Private Celebration": "Acara Privat",
  "Birthdays · anniversaries · dinners": "Ulang tahun · anniversary · dinner",
  "Corporate / Brand Event": "Event Korporat / Brand",
  "Launches · activations · gatherings": "Launch · activation · gathering",
  "Stage · technical · run of show": "Stage · teknis · run of show",
  "Other": "Lainnya",
  "Tell us what you have in mind": "Ceritakan apa yang Anda bayangkan",
  "City / Venue": "Kota / Venue",
  "Event date": "Tanggal event",
  "Estimated guests": "Perkiraan tamu",
  "Select a date": "Pilih tanggal",
  "Choose event date": "Pilih tanggal event",
  "Previous month": "Bulan sebelumnya",
  "Next month": "Bulan berikutnya",
  "Decrease guests": "Kurangi jumlah tamu",
  "Increase guests": "Tambah jumlah tamu",
  "Tell us what matters. We’ll take it from there.": "Ceritakan yang penting. Selebihnya biar kami yang urus.",
  "Package added to brief": "Paket ditambahkan ke brief",
  "Remove ×": "Hapus ×",
  "Direction added to brief": "Arah kreatif ditambahkan ke brief",
  "Tell us about it *": "Ceritakan event Anda *",
  "Prepare my brief": "Siapkan brief saya",
  "Contact": "Kontak",
  "HOME BASE": "HOME BASE",
  "East Java, Indonesia": "Jawa Timur, Indonesia",
  "重ね / Layer with intention": "重ね / Menyusun dengan niat",
  "Back to top ↑": "Kembali ke atas ↑",
  "KASANE / DIRECTION": "KASANE / ARAH KREATIF",
  "Wedding direction": "Arah kreatif wedding",
  "Celebration direction": "Arah kreatif perayaan",
  "Production direction": "Arah produksi",
  "Private direction": "Arah privat",
  "Best for": "Cocok untuk",
  "The feeling": "Nuansa",
  "Put this on my brief": "Tambahkan ke brief saya",
  "We’ll carry this direction into your inquiry. It is a starting point, not a fixed package.": "Arah ini akan kami bawa ke inquiry Anda. Ini adalah titik awal, bukan paket yang kaku.",
  "KASANE / SCOPE": "KASANE / SCOPE",
  "Brief this service": "Masukkan layanan ini ke brief",
  "KASANE works best with JavaScript enabled for navigation, animations and the event board.": "KASANE bekerja paling baik dengan JavaScript aktif untuk navigasi, animasi, dan event board.",
  "Your name": "Nama Anda",
  "Malang, Surabaya, venue TBD...": "Malang, Surabaya, venue TBD...",
  "e.g. 300": "contoh: 300",
  "What should the event feel like? What do you already know, and where do you need help?": "Seperti apa event ini ingin terasa? Apa yang sudah Anda ketahui, dan di bagian mana Anda membutuhkan bantuan?",
  "Open menu": "Buka menu",
  "Close": "Tutup",
  "Close creative direction details": "Tutup detail arah kreatif",
  "Close service details": "Tutup detail layanan",
  "Event type": "Jenis event",
  "Scale": "Skala",
  "Focus": "Fokus",
  "Remove selected package": "Hapus paket terpilih",
  "Remove selected direction": "Hapus arah kreatif terpilih",
  "300 GUESTS": "300 TAMU",
  "FULL SERVICE": "FULL SERVICE",
  "FULL PLANNING · CEREMONY TO FINAL CUE": "FULL PLANNING · CEREMONY HINGGA CUE TERAKHIR",
  "One calm production system around one very personal day.": "Satu sistem produksi yang tenang untuk satu hari yang sangat personal.",
  "180 GUESTS": "180 TAMU",
  "SHOW FLOW": "ALUR ACARA",
  "CONCEPT · ENTRANCE · DINNER · PARTY": "KONSEP · ENTRANCE · DINNER · PARTY",
  "A celebration that feels current, personal, and never like a generic package.": "Perayaan yang terasa current, personal, dan tidak pernah seperti paket generik.",
  "80 GUESTS": "80 TAMU",
  "ATMOSPHERE": "SUASANA",
  "DINNER · DETAIL · MUSIC · GUEST JOURNEY": "DINNER · DETAIL · MUSIK · PERJALANAN TAMU",
  "Intimate does not mean simple—it means every detail is more visible.": "Intim bukan berarti sederhana—justru setiap detail menjadi lebih terlihat.",
  "BRAND EVENT": "BRAND EVENT",
  "250 PAX": "250 PAX",
  "EXPERIENCE": "PENGALAMAN",
  "LAUNCH · ACTIVATION · CONTENT · HOSPITALITY": "LAUNCH · ACTIVATION · CONTENT · HOSPITALITY",
  "Brand objectives translated into a physical experience people can actually feel.": "Tujuan brand diterjemahkan menjadi pengalaman fisik yang benar-benar dapat dirasakan tamu.",
  "600 PAX": "600 PAX",
  "TECHNICAL": "TEKNIS",
  "STAGE · LIGHTING · AUDIO · RUN OF SHOW": "STAGE · LIGHTING · AUDIO · RUN OF SHOW",
  "Technical control, vendor coordination, and cue-by-cue execution behind the visible moment.": "Kontrol teknis, koordinasi vendor, dan eksekusi cue-by-cue di balik momen yang terlihat.",
  "A restrained wedding world where the room feels expensive because every layer is controlled: proportion, texture, lighting, pacing and hospitality. Nothing needs to shout for the event to feel special.": "Dunia wedding yang restrained, di mana ruangan terasa premium karena setiap lapisan dikontrol: proporsi, tekstur, lighting, pacing, dan hospitality. Tidak perlu berteriak untuk terasa istimewa.",
  "Wedding · engagement dinner · elegant reception": "Wedding · engagement dinner · resepsi elegan",
  "Warm · tactile · restrained · polished": "Hangat · tactile · restrained · polished",
  "Use fewer gestures, then make every one of them intentional.": "Gunakan lebih sedikit gesture, lalu buat semuanya terasa disengaja.",
  "Built around the shift from dinner into a real night out: darker lighting, a stronger music arc, movement, entrance moments and a room that becomes more alive as the program progresses.": "Dibangun dari transisi dinner menuju malam yang benar-benar hidup: lighting lebih gelap, alur musik lebih kuat, movement, entrance moment, dan ruangan yang makin hidup seiring acara berjalan.",
  "Sweet Seventeen · birthday · evening celebration": "Sweet Seventeen · ulang tahun · perayaan malam",
  "Moody · social · kinetic · cinematic": "Moody · sosial · dinamis · cinematic",
  "The room should change with the night instead of staying visually flat.": "Ruangan harus ikut berubah sepanjang malam, bukan tetap terasa visualnya datar.",
  "A production-led direction for events where timing, reveal, lighting and technical cues are part of the experience. The spectacle works because the backstage system is precise.": "Arah yang dipimpin produksi untuk event di mana timing, reveal, lighting, dan cue teknis menjadi bagian dari pengalaman. Spektakelnya bekerja karena sistem backstage-nya presisi.",
  "Brand event · Sweet Seventeen · launch · stage program": "Brand event · Sweet Seventeen · launch · stage program",
  "Bold · timed · technical · high-impact": "Bold · terukur · teknis · high-impact",
  "A big moment only feels effortless when every cue underneath it is disciplined.": "Momen besar hanya terasa effortless ketika setiap cue di baliknya disiplin.",
  "An intimate, hospitality-first direction where the guest list stays close and the details carry more emotional weight: long dinner, softer light, meaningful objects and enough time for the room to breathe.": "Arah yang intim dan hospitality-first, dengan daftar tamu yang dekat dan detail yang membawa bobot emosional lebih besar: dinner panjang, cahaya lebih lembut, objek bermakna, dan waktu agar ruangan dapat bernapas.",
  "Private dinner · anniversary · intimate wedding": "Private dinner · anniversary · intimate wedding",
  "Intimate · warm · personal · unhurried": "Intim · hangat · personal · tidak terburu-buru",
  "When the guest list is smaller, every touchpoint becomes more visible.": "Ketika jumlah tamu lebih kecil, setiap touchpoint menjadi lebih terlihat.",
  "From planning architecture to on-the-day control, we keep the wedding personal while the production stays disciplined.": "Dari arsitektur planning hingga kontrol hari-H, kami menjaga wedding tetap personal sementara produksinya tetap disiplin.",
  "Planning": "Planning",
  "Master timeline · scope · budget structure": "Master timeline · scope · struktur budget",
  "Creative": "Kreatif",
  "Event language · styling direction · guest journey": "Bahasa event · arah styling · perjalanan tamu",
  "Coordination": "Koordinasi",
  "Venue · vendors · family · rehearsals": "Venue · vendor · keluarga · rehearsal",
  "Run of show · cues · technical handoff": "Run of show · cue · handoff teknis",
  "A milestone designed around personality—not a copy-paste theme—with enough production structure to make the night move.": "Sebuah milestone yang dibangun dari personality—bukan tema copy-paste—dengan struktur produksi yang cukup kuat agar malam terus bergerak.",
  "Concept": "Konsep",
  "Visual world · entrance · program": "Dunia visual · entrance · program",
  "Experience": "Experience",
  "Guest flow · dinner · party energy": "Alur tamu · dinner · energi party",
  "Talent": "Talent",
  "MC · entertainment · performers": "MC · entertainment · performer",
  "Stage · lighting · sound · cue sheet": "Stage · lighting · sound · cue sheet",
  "Smaller guest lists allow every touchpoint to matter more. We shape the atmosphere, flow and details around the people in the room.": "Jumlah tamu yang lebih kecil membuat setiap touchpoint lebih berarti. Kami membentuk atmosfer, alur, dan detail di sekitar orang-orang yang hadir.",
  "Occasions": "Acara",
  "Tablescape · mood · hospitality": "Tablescape · mood · hospitality",
  "Vendor coordination · timeline": "Koordinasi vendor · timeline",
  "On-site": "On-site",
  "Setup · guest flow · show control": "Setup · alur tamu · kontrol acara",
  "For launches, dinners and gatherings where the environment needs to carry the brand as strongly as the content.": "Untuk launch, dinner, dan gathering di mana lingkungan acara harus membawa brand sekuat kontennya.",
  "Strategy": "Strategi",
  "Objective · audience · event narrative": "Tujuan · audiens · narasi event",
  "Spatial flow · brand touchpoints": "Alur ruang · touchpoint brand",
  "Hospitality": "Hospitality",
  "Guest handling · dining · gifting": "Penanganan tamu · dining · gifting",
  "Delivery": "Delivery",
  "Vendors · technical · program control": "Vendor · teknis · kontrol program",
  "The backstage layer: practical, technical and cue-driven support for events that need execution discipline.": "Lapisan backstage: dukungan praktis, teknis, dan cue-driven untuk event yang membutuhkan disiplin eksekusi.",
  "Technical": "Teknis",
  "Stage · sound · lighting · screen": "Stage · sound · lighting · screen",
  "Vendors": "Vendor",
  "Sourcing · scope · coordination": "Sourcing · scope · koordinasi",
  "Show": "Show",
  "Run of show · cue calling · rehearsal": "Run of show · cue calling · rehearsal",
  "Site": "Site",
  "Load-in · setup · strike · contingency": "Load-in · setup · strike · contingency",
  "Please complete the required fields before preparing the brief.": "Mohon lengkapi field wajib sebelum menyiapkan brief.",
  "Opening your message now.": "Membuka pesan Anda sekarang.",
  "Direction reference:": "Referensi arah kreatif:",
  "What I want to keep / change from this direction:": "Bagian yang ingin saya pertahankan / ubah dari arah ini:",
  "Package preference:": "Preferensi paket:",
  "What I already know about the event:": "Hal yang sudah saya ketahui tentang event ini:",
  "04 / WHY KASANE": "04 / KENAPA KASANE",
  "Seamless is not luck.": "Seamless bukan kebetulan.",
  "It is coordination.": "Itu hasil koordinasi.",
  "Your event should feel like one experience—not eight separate vendor conversations. KASANE keeps the decisions, people, timing and production connected behind the scenes.": "Acara Anda harus terasa sebagai satu pengalaman—bukan delapan percakapan vendor yang terpisah. KASANE menjaga keputusan, orang, timing, dan produksi tetap terhubung di balik layar.",
  "01 / ONE POINT OF CONTACT": "01 / SATU TITIK KONTAK",
  "One team holding the whole picture.": "Satu tim yang memegang gambaran besarnya.",
  "Instead of managing every supplier separately, you have one KASANE team keeping the brief, priorities, timeline and handoffs aligned.": "Daripada mengelola setiap vendor secara terpisah, Anda memiliki satu tim KASANE yang menjaga brief, prioritas, timeline, dan handoff tetap selaras.",
  "02 / VENDOR ORCHESTRATION": "02 / ORKESTRASI VENDOR",
  "The right partners, working as one.": "Partner yang tepat, bekerja sebagai satu tim.",
  "We can source the venue and vendors, compare options, coordinate communication and make sure every supplier is working toward the same event plan.": "Kami dapat mencarikan venue dan vendor, membandingkan pilihan, mengoordinasikan komunikasi, dan memastikan setiap partner bekerja menuju rencana acara yang sama.",
  "03 / EVENT-DAY CONTROL": "03 / KONTROL HARI-H",
  "Calm in front. Control behind it.": "Tenang di depan. Terkontrol di belakang.",
  "Setup, guest flow, vendor arrivals, technical cues, rehearsals, contingency and run of show stay owned—so you are not solving production problems during your own event.": "Setup, alur tamu, kedatangan vendor, cue teknis, rehearsal, contingency, dan run of show tetap terkontrol—agar Anda tidak perlu menyelesaikan masalah produksi di acara Anda sendiri.",
  "THE LAYERS WE CAN HANDLE": "LAPISAN YANG DAPAT KAMI TANGANI",
  "From venue search": "Dari pencarian venue",
  "to final cue.": "hingga cue terakhir.",
  "KASANE can source, brief and coordinate the partners your event needs. You can bring your own vendors too—we integrate them into the same working plan.": "KASANE dapat mencari, memberi brief, dan mengoordinasikan partner yang dibutuhkan acara Anda. Anda juga dapat membawa vendor pilihan sendiri—kami integrasikan semuanya ke dalam satu rencana kerja.",
  "Event vendor and production layers KASANE can handle": "Lapisan vendor dan produksi yang dapat ditangani KASANE",
  "Search · shortlist · site coordination": "Pencarian · shortlist · koordinasi lokasi",
  "Brief · tasting flow · service timing": "Brief · alur tasting · timing service",
  "Décor & Styling": "Dekorasi & Styling",
  "Creative brief · layout · installation": "Creative brief · layout · instalasi",
  "Coverage brief · timeline · key moments": "Brief coverage · timeline · momen penting",
  "Talent · repertoire · stage timing": "Talent · repertoire · timing panggung",
  "Program brief · script flow · cues": "Brief program · alur script · cue",
  "Stage · sound · lighting · screens": "Stage · sound · lighting · screen",
  "Guest & Event Operations": "Operasional Tamu & Event",
  "Rundown · guest flow · on-site control": "Rundown · alur tamu · kontrol on-site",
  "KASANE / ONE CONNECTED PLAN": "KASANE / SATU RENCANA TERHUBUNG",
  "No client should have to chase eight vendors on event day.": "Tidak seharusnya klien mengejar delapan vendor di hari acaranya sendiri.",
  "Start with one brief": "Mulai dari satu brief",
  "05 / THE KASANE BOARD": "05 / KASANE EVENT BOARD",
  "06 / CREATIVE DIRECTION": "06 / ARAH KREATIF",
  "07 / HOW WE WORK": "07 / CARA KAMI BEKERJA",
  "Can you help us find the venue and vendors?": "Bisakah KASANE membantu mencari venue dan vendor?",
  "Yes. KASANE can help source and coordinate hotels or venues, catering, décor, photo and videography, entertainment, MC or talent, and technical production based on the event brief and agreed scope.": "Ya. KASANE dapat membantu mencari dan mengoordinasikan hotel atau venue, catering, dekorasi, foto dan videografi, entertainment, MC atau talent, serta produksi teknis berdasarkan brief dan scope yang disepakati.",
  "Can we use vendors we already chose?": "Bisakah kami tetap memakai vendor yang sudah dipilih?",
  "Yes. Existing vendors can stay part of the event. We bring them into the same timeline, communication flow and production plan so responsibilities remain clear.": "Ya. Vendor yang sudah dipilih tetap dapat menjadi bagian dari acara. Kami memasukkan mereka ke timeline, alur komunikasi, dan rencana produksi yang sama agar tanggung jawab tetap jelas.",
  "Do we need a venue before contacting KASANE?": "Apakah kami harus sudah punya venue sebelum menghubungi KASANE?",
  "No. Your venue can still be TBD. If venue sourcing is part of the scope, we can start from the city, guest count, event style and practical requirements.": "Tidak. Venue Anda boleh masih TBD. Jika pencarian venue termasuk dalam scope, kami dapat mulai dari kota, jumlah tamu, gaya acara, dan kebutuhan praktisnya.",
  "An invitation that already feels like": "Undangan yang sudah terasa seperti",
  "the event.": "acaranya.",
  "Personalized guest links, RSVP, wishes, countdown, maps and music—designed as part of the same visual world as your celebration, not as a generic add-on.": "Tautan personal untuk setiap tamu, RSVP, ucapan, countdown, maps, dan musik—dirancang sebagai bagian dari dunia visual acara Anda, bukan sekadar tambahan generik.",
  "Personalized for every guest": "Personal untuk setiap tamu",
  "Mobile-first & responsive": "Mobile-first & responsif",
  "RSVP + wishes": "RSVP + ucapan",
  "Music + event details": "Musik + detail acara",
  "Open sample invitation": "Buka contoh undangan",
  "Open KASANE MUSUBI sample for Alya Prasetyo": "Buka contoh KASANE MUSUBI untuk Alya Prasetyo",
  "THE WEDDING OF": "PERNIKAHAN",
  "PREPARED FOR": "UNTUK",
  "OPEN INVITATION": "BUKA UNDANGAN"
};
  let currentLanguage = (() => {
    const requested = new URLSearchParams(location.search).get('lang');
    if (requested === 'id' || requested === 'en') return requested;
    try { return localStorage.getItem('kasane-language') === 'id' ? 'id' : 'en'; } catch (_) { return 'en'; }
  })();
  const originalText = new WeakMap();
  const originalAttrs = new WeakMap();
  const tr = (text) => currentLanguage === 'id' ? (idTranslations[text] || text) : text;

  const translateTextNodes = () => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.parentElement || ['SCRIPT','STYLE','NOSCRIPT'].includes(node.parentElement.tagName)) return NodeFilter.FILTER_REJECT;
        return node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      if (!originalText.has(node)) originalText.set(node, node.nodeValue);
      const original = originalText.get(node);
      const key = original.trim();
      const translated = currentLanguage === 'id' ? (idTranslations[key] || key) : key;
      const lead = original.match(/^\s*/)?.[0] || '';
      const tail = original.match(/\s*$/)?.[0] || '';
      node.nodeValue = `${lead}${translated}${tail}`;
    });

    document.querySelectorAll('[placeholder],[aria-label],[title]').forEach(el => {
      if (!originalAttrs.has(el)) originalAttrs.set(el, {});
      const saved = originalAttrs.get(el);
      ['placeholder','aria-label','title'].forEach(attr => {
        if (!el.hasAttribute(attr)) return;
        if (!(attr in saved)) saved[attr] = el.getAttribute(attr);
        const base = saved[attr];
        el.setAttribute(attr, currentLanguage === 'id' ? (idTranslations[base] || base) : base);
      });
    });
  };

  const renderMarqueeLanguage = () => {
    const belt = document.querySelector('[data-marquee-belt]');
    if (!belt) return;
    const words = currentLanguage === 'id'
      ? ['WEDDING','SWEET SEVENTEEN','ACARA PRIVAT','ACARA KORPORAT','BRAND EXPERIENCE','PRODUKSI']
      : ['WEDDINGS','SWEET SEVENTEENS','PRIVATE CELEBRATIONS','CORPORATE EVENTS','BRAND EXPERIENCES','PRODUCTION'];
    belt.innerHTML = words.map(word => `<span>${word}</span><i>✦</i>`).join('');
    delete belt.dataset.seedHtml;
    window.kasaneRebuildMarquee?.();
  };

  const updateLanguageButtons = () => {
    document.documentElement.lang = currentLanguage === 'id' ? 'id' : 'en';
    document.documentElement.dataset.lang = currentLanguage;
    document.querySelectorAll('[data-lang-toggle]').forEach(button => {
      const isId = currentLanguage === 'id';
      button.setAttribute('aria-pressed', String(isId));
      button.setAttribute('aria-label', isId ? 'Switch language to English' : 'Ganti bahasa ke Bahasa Indonesia');
    });
    document.title = currentLanguage === 'id'
      ? 'KASANE COLLECTIVE — Event · Experience · Produksi'
      : 'KASANE COLLECTIVE — Events · Experiences · Production';
  };

  const applyLanguage = (lang, { persist = true } = {}) => {
    currentLanguage = lang === 'id' ? 'id' : 'en';
    if (persist) { try { localStorage.setItem('kasane-language', currentLanguage); } catch (_) {} }
    translateTextNodes();
    renderMarqueeLanguage();
    updateLanguageButtons();
    window.dispatchEvent(new CustomEvent('kasane:languagechange', { detail: { language: currentLanguage } }));
  };

  document.querySelectorAll('[data-lang-toggle]').forEach(button => button.addEventListener('click', () => applyLanguage(currentLanguage === 'en' ? 'id' : 'en')));
  applyLanguage(currentLanguage, { persist: false });

  const smoothTo = (target) => target?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });

  /* Navigation */
  const setNav = () => nav?.classList.toggle('is-scrolled', window.scrollY > 28);
  setNav();
  addEventListener('scroll', setNav, { passive: true });

  const setMenu = (open) => {
    mobileMenu?.classList.toggle('is-open', open);
    menuToggle?.classList.toggle('is-active', open);
    menuToggle?.setAttribute('aria-expanded', String(open));
    mobileMenu?.setAttribute('aria-hidden', String(!open));
    if (mobileMenu) mobileMenu.inert = !open;
    body.classList.toggle('menu-open', open);
  };
  menuToggle?.addEventListener('click', () => setMenu(!mobileMenu.classList.contains('is-open')));
  mobileMenu?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));

  /* Hero gallery */
  const slides = [...document.querySelectorAll('.hero-slide')];
  const heroCurrent = document.getElementById('heroCurrent');
  let heroIndex = 0;
  let heroTimer = null;
  const advanceHero = () => {
    if (document.hidden || slides.length < 2) return;
    slides[heroIndex].classList.remove('is-active');
    heroIndex = (heroIndex + 1) % slides.length;
    slides[heroIndex].classList.add('is-active');
    if (heroCurrent) heroCurrent.textContent = String(heroIndex + 1).padStart(2, '0');
  };
  const startHeroTimer = () => {
    if (reduceMotion || slides.length < 2 || heroTimer) return;
    heroTimer = window.setInterval(advanceHero, 5600);
  };
  const stopHeroTimer = () => {
    if (!heroTimer) return;
    clearInterval(heroTimer);
    heroTimer = null;
  };
  startHeroTimer();
  document.addEventListener('visibilitychange', () => document.hidden ? stopHeroTimer() : startHeroTimer());

  /* Reveal */
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -7% 0px' });
    reveals.forEach(el => io.observe(el));
  } else {
    reveals.forEach(el => el.classList.add('is-visible'));
  }

  (() => {
    const band = document.querySelector('[data-marquee]');
    const track = band?.querySelector('[data-marquee-track]');
    let belt = band?.querySelector('[data-marquee-belt]');
    if (!band || !track || !belt) return;

    let resizeTimer;

    const rebuild = () => {
      track.querySelectorAll('[data-marquee-clone]').forEach(node => node.remove());
      belt = track.querySelector('[data-marquee-belt]');
      if (!belt) return;

      if (!belt.dataset.seedHtml) belt.dataset.seedHtml = belt.innerHTML.trim();
      belt.innerHTML = belt.dataset.seedHtml;

      const minimum = Math.max(band.clientWidth * 1.45, band.clientWidth + 420);
      let guard = 0;
      while (belt.scrollWidth < minimum && guard < 12) {
        belt.insertAdjacentHTML('beforeend', belt.dataset.seedHtml);
        guard += 1;
      }

      const clone = belt.cloneNode(true);
      clone.removeAttribute('data-marquee-belt');
      clone.dataset.marqueeClone = 'true';
      clone.setAttribute('aria-hidden', 'true');
      track.appendChild(clone);

      const distance = belt.getBoundingClientRect().width;
      const speed = Math.max(28, Number(band.dataset.speed) || 58);
      const duration = distance / speed;

      band.classList.remove('is-running');
      track.style.animation = 'none';
      track.style.transform = 'translate3d(0,0,0)';
      track.style.setProperty('--marquee-shift', `${-distance}px`);
      track.style.setProperty('--marquee-duration', `${duration.toFixed(3)}s`);
      void track.offsetWidth;
      track.style.animation = '';
      if (!motionQuery.matches) band.classList.add('is-running');
    };

    window.kasaneRebuildMarquee = rebuild;
    requestAnimationFrame(rebuild);
    document.fonts?.ready?.then(rebuild).catch(() => {});
    addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(rebuild, 170);
    });
    motionQuery.addEventListener?.('change', rebuild);
  })();

  /* Split flap + synthesized click-clack */
  const flapAlphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /–';
  const boardEvents = [
    { event: 'WEDDING', scale: '300 GUESTS', focus: 'FULL SERVICE', note: 'FULL PLANNING · CEREMONY TO FINAL CUE', kicker: 'Wedding Organization', detail: 'One calm production system around one very personal day.' },
    { event: 'SWEET 17', scale: '180 GUESTS', focus: 'SHOW FLOW', note: 'CONCEPT · ENTRANCE · DINNER · PARTY', kicker: 'Sweet Seventeen', detail: 'A celebration that feels current, personal, and never like a generic package.' },
    { event: 'PRIVATE', scale: '80 GUESTS', focus: 'ATMOSPHERE', note: 'DINNER · DETAIL · MUSIC · GUEST JOURNEY', kicker: 'Private Celebration', detail: 'Intimate does not mean simple—it means every detail is more visible.' },
    { event: 'BRAND EVENT', scale: '250 PAX', focus: 'EXPERIENCE', note: 'LAUNCH · ACTIVATION · CONTENT · HOSPITALITY', kicker: 'Brand & Corporate', detail: 'Brand objectives translated into a physical experience people can actually feel.' },
    { event: 'PRODUCTION', scale: '600 PAX', focus: 'TECHNICAL', note: 'STAGE · LIGHTING · AUDIO · RUN OF SHOW', kicker: 'Event Production', detail: 'Technical control, vendor coordination, and cue-by-cue execution behind the visible moment.' }
  ];

  const flapEvent = document.querySelector('[data-flap-event]');
  const flapScale = document.querySelector('[data-flap-scale]');
  const flapFocus = document.querySelector('[data-flap-focus]');
  const boardNumber = document.querySelector('[data-board-number]');
  const boardNote = document.querySelector('[data-board-note]');
  const boardKicker = document.querySelector('[data-board-kicker]');
  const boardDetail = document.querySelector('[data-board-detail]');
  const prev = document.querySelector('[data-board-prev]');
  const next = document.querySelector('[data-board-next]');
  const play = document.querySelector('[data-board-play]');
  const sound = document.querySelector('[data-board-sound]');
  const clock = document.querySelector('[data-board-clock]');
  let boardIndex = 0;
  let autoplay = true;
  let soundEnabled = true;
  let audioContext = null;
  let audioUnlocked = false;
  let timer;

  const updateClock = () => {
    if (!clock) return;
    clock.textContent = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());
  };
  updateClock();
  setInterval(updateClock, 15000);

  const unlockAudio = async () => {
    if (!soundEnabled) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!audioContext) audioContext = new AC();
    try {
      if (audioContext.state === 'suspended') await audioContext.resume();
      audioUnlocked = audioContext.state === 'running';
    } catch (_) {}
  };

  const clack = (tone = 0) => {
    if (!soundEnabled || !audioUnlocked || !audioContext || reduceMotion) return;
    const now = audioContext.currentTime;
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    const filter = audioContext.createBiquadFilter();
    osc.type = 'square';
    osc.frequency.setValueAtTime(900 + (tone % 5) * 70, now);
    filter.type = 'bandpass';
    filter.frequency.value = 1200;
    filter.Q.value = 1.2;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.035, now + .002);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + .028);
    osc.connect(filter).connect(gain).connect(audioContext.destination);
    osc.start(now);
    osc.stop(now + .032);
  };

  const createTile = (char = ' ') => {
    const tile = document.createElement('span');
    tile.className = 'flap-char';
    tile.dataset.char = char;
    tile.innerHTML = `<span class="flap-half flap-top"><span>${char}</span></span><span class="flap-half flap-bottom"><span>${char}</span></span><span class="flap-flip flap-flip--top"><span>${char}</span></span><span class="flap-flip flap-flip--bottom"><span>${char}</span></span>`;
    return tile;
  };

  const setupFlap = (el, length) => {
    if (!el) return;
    const frag = document.createDocumentFragment();
    for (let i = 0; i < length; i += 1) {
      frag.appendChild(createTile(reduceMotion ? ' ' : flapAlphabet[Math.floor(Math.random() * flapAlphabet.length)]));
    }
    el.replaceChildren(frag);
  };

  const flipChar = (tile, nextChar, delay, soundIndex) => {
    const current = tile.dataset.char || ' ';
    if (current === nextChar) return;
    const top = tile.querySelector('.flap-top span');
    const bottom = tile.querySelector('.flap-bottom span');
    const flipTop = tile.querySelector('.flap-flip--top span');
    const flipBottom = tile.querySelector('.flap-flip--bottom span');

    if (reduceMotion) {
      [top, bottom, flipTop, flipBottom].forEach(el => { if (el) el.textContent = nextChar; });
      tile.dataset.char = nextChar;
      return;
    }

    setTimeout(() => {
      if (top) top.textContent = nextChar;
      if (bottom) bottom.textContent = current;
      if (flipTop) flipTop.textContent = current;
      if (flipBottom) flipBottom.textContent = nextChar;
      tile.classList.remove('is-flipping');
      void tile.offsetWidth;
      tile.classList.add('is-flipping');
      if (soundIndex % 2 === 0) clack(soundIndex);
      setTimeout(() => {
        if (bottom) bottom.textContent = nextChar;
        if (flipTop) flipTop.textContent = nextChar;
        tile.dataset.char = nextChar;
        tile.classList.remove('is-flipping');
      }, 430);
    }, delay);
  };

  const setFlapText = (el, text, baseDelay = 0) => {
    if (!el) return;
    const tiles = [...el.querySelectorAll('.flap-char')];
    const normalized = text.toUpperCase().padEnd(tiles.length, ' ').slice(0, tiles.length);
    tiles.forEach((tile, i) => flipChar(tile, normalized[i], baseDelay + i * 28, i));
    el.setAttribute('aria-label', text);
  };

  setupFlap(flapEvent, 12);
  setupFlap(flapScale, 10);
  setupFlap(flapFocus, 12);

  const paintBoard = () => {
    const item = boardEvents[boardIndex];
    setFlapText(flapEvent, tr(item.event), 0);
    setFlapText(flapScale, tr(item.scale), 100);
    setFlapText(flapFocus, tr(item.focus), 190);
    if (boardNumber) boardNumber.textContent = `${String(boardIndex + 1).padStart(2, '0')} / ${String(boardEvents.length).padStart(2, '0')}`;
    if (boardNote) boardNote.textContent = tr(item.note);
    if (boardKicker) boardKicker.textContent = tr(item.kicker);
    if (boardDetail) boardDetail.textContent = tr(item.detail);
  };

  const resetTimer = () => {
    clearInterval(timer);
    if (autoplay && !reduceMotion) {
      timer = setInterval(() => {
        boardIndex = (boardIndex + 1) % boardEvents.length;
        paintBoard();
      }, 5200);
    }
  };

  const moveBoard = async (delta) => {
    await unlockAudio();
    boardIndex = (boardIndex + delta + boardEvents.length) % boardEvents.length;
    paintBoard();
    resetTimer();
  };

  prev?.addEventListener('click', () => moveBoard(-1));
  next?.addEventListener('click', () => moveBoard(1));
  document.querySelector('[data-event-board]')?.addEventListener('pointerdown', unlockAudio, { once: true });
  play?.addEventListener('click', async () => {
    await unlockAudio();
    autoplay = !autoplay;
    play.textContent = tr(autoplay ? 'Pause' : 'Play');
    resetTimer();
  });
  sound?.addEventListener('click', async () => {
    soundEnabled = !soundEnabled;
    sound.setAttribute('aria-pressed', String(soundEnabled));
    sound.querySelector('b').textContent = soundEnabled ? 'ON' : 'OFF';
    if (soundEnabled) {
      await unlockAudio();
      clack(1);
    }
  });
  paintBoard();
  resetTimer();
  window.addEventListener('kasane:languagechange', () => {
    paintBoard();
    if (play) play.textContent = tr(autoplay ? 'Pause' : 'Play');
  });

  /* Inquiry form */
  const CONFIG = window.KASANE_CONFIG || {};
  const CONTACT_EMAIL = CONFIG.contactEmail || 'hello@kasanecollective.com';
  const BRIEF_ENDPOINT = String(CONFIG.briefEndpoint || '').trim();
  const REQUEST_TIMEOUT_MS = Number(CONFIG.requestTimeoutMs || 12000);
  const TURNSTILE_SITE_KEY = String(CONFIG.turnstileSiteKey || '').trim();
  const TURNSTILE_ACTION = String(CONFIG.turnstileAction || 'kasane_brief').trim();
  const form = document.getElementById('briefForm');
  const status = document.getElementById('formStatus');
  const eventSelect = form?.querySelector('select[name="event"]');
  const customSelect = document.querySelector('[data-custom-select]');
  const selectTrigger = customSelect?.querySelector('[data-custom-select-trigger]');
  const selectValue = customSelect?.querySelector('[data-custom-select-value]');
  const selectOptions = [...(customSelect?.querySelectorAll('[data-select-option]') || [])];
  const messageField = form?.querySelector('textarea[name="message"]');
  const briefSelection = document.getElementById('briefSelection');
  const briefSelectionTitle = document.getElementById('briefSelectionTitle');
  const briefSelectionRemove = document.getElementById('briefSelectionRemove');
  const briefDirection = document.getElementById('briefDirection');
  const productSelection = document.getElementById('productSelection');
  const productSelectionTitle = document.getElementById('productSelectionTitle');
  const productSelectionRemove = document.getElementById('productSelectionRemove');
  const briefProduct = document.getElementById('briefProduct');
  const packageSelection = document.getElementById('packageSelection');
  const packageSelectionTitle = document.getElementById('packageSelectionTitle');
  const packageSelectionRemove = document.getElementById('packageSelectionRemove');
  const briefPackage = document.getElementById('briefPackage');

  const datePicker = form?.querySelector('[data-date-picker]');
  const dateTrigger = datePicker?.querySelector('[data-date-trigger]');
  const dateValue = datePicker?.querySelector('[data-date-value]');
  const dateInput = datePicker?.querySelector('[data-date-input]');
  const datePopover = datePicker?.querySelector('[data-date-popover]');
  const dateMonth = datePicker?.querySelector('[data-date-month]');
  const dateWeekdays = datePicker?.querySelector('[data-date-weekdays]');
  const dateDays = datePicker?.querySelector('[data-date-days]');
  const datePrev = datePicker?.querySelector('[data-date-prev]');
  const dateNext = datePicker?.querySelector('[data-date-next]');
  const today = new Date();
  today.setHours(0,0,0,0);
  let calendarView = new Date(today.getFullYear(), today.getMonth(), 1);

  const isoLocal = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const parseIsoLocal = (value) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
    const [y,m,d] = value.split('-').map(Number);
    const parsed = new Date(y, m - 1, d);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const formatSelectedDate = (date) => {
    const locale = currentLanguage === 'id' ? 'id-ID' : 'en-GB';
    return new Intl.DateTimeFormat(locale, { day:'2-digit', month:'short', year:'numeric' }).format(date).replace(/\./g,'').toUpperCase();
  };

  const renderCalendar = () => {
    if (!dateDays || !dateMonth || !dateWeekdays) return;
    const locale = currentLanguage === 'id' ? 'id-ID' : 'en-US';
    dateMonth.textContent = new Intl.DateTimeFormat(locale, { month:'long', year:'numeric' }).format(calendarView);
    const weekdays = currentLanguage === 'id' ? ['Min','Sen','Sel','Rab','Kam','Jum','Sab'] : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    dateWeekdays.replaceChildren(...weekdays.map(day => { const el=document.createElement('span'); el.textContent=day; return el; }));
    dateDays.replaceChildren();
    const year = calendarView.getFullYear();
    const month = calendarView.getMonth();
    const first = new Date(year, month, 1);
    const total = new Date(year, month + 1, 0).getDate();
    for (let i=0; i<first.getDay(); i++) dateDays.append(document.createElement('i'));
    const selected = dateInput?.value || '';
    for (let day=1; day<=total; day++) {
      const date = new Date(year, month, day);
      const iso = isoLocal(date);
      const button = document.createElement('button');
      button.type='button';
      button.textContent=String(day);
      button.dataset.calendarDate=iso;
      button.setAttribute('aria-label', new Intl.DateTimeFormat(locale, { weekday:'long', day:'numeric', month:'long', year:'numeric' }).format(date));
      if (date < today) button.disabled = true;
      if (iso === selected) button.classList.add('is-selected');
      if (iso === isoLocal(today)) button.classList.add('is-today');
      dateDays.append(button);
    }
  };

  const updateDateDisplay = () => {
    if (!dateValue) return;
    const selected = parseIsoLocal(dateInput?.value || '');
    dateValue.textContent = selected ? formatSelectedDate(selected) : tr('Select a date');
    dateValue.classList.toggle('is-placeholder', !selected);
  };

  const closeDatePicker = () => {
    if (!datePicker || !datePopover) return;
    datePicker.classList.remove('is-open');
    datePopover.hidden = true;
    dateTrigger?.setAttribute('aria-expanded','false');
  };
  const openDatePicker = () => {
    if (!datePicker || !datePopover) return;
    const selected = parseIsoLocal(dateInput?.value || '');
    if (selected) calendarView = new Date(selected.getFullYear(), selected.getMonth(), 1);
    else calendarView = new Date(today.getFullYear(), today.getMonth(), 1);
    renderCalendar();
    datePopover.hidden = false;
    datePicker.classList.add('is-open');
    dateTrigger?.setAttribute('aria-expanded','true');
  };

  dateTrigger?.addEventListener('click', () => datePicker?.classList.contains('is-open') ? closeDatePicker() : openDatePicker());
  datePrev?.addEventListener('click', () => { calendarView = new Date(calendarView.getFullYear(), calendarView.getMonth()-1, 1); renderCalendar(); });
  dateNext?.addEventListener('click', () => { calendarView = new Date(calendarView.getFullYear(), calendarView.getMonth()+1, 1); renderCalendar(); });
  dateDays?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-calendar-date]');
    if (!button || button.disabled || !dateInput) return;
    dateInput.value = button.dataset.calendarDate || '';
    dateInput.dispatchEvent(new Event('change', { bubbles:true }));
    updateDateDisplay();
    closeDatePicker();
    dateTrigger?.focus();
  });
  document.addEventListener('pointerdown', (event) => {
    if (datePicker?.classList.contains('is-open') && !datePicker.contains(event.target)) closeDatePicker();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && datePicker?.classList.contains('is-open')) { closeDatePicker(); dateTrigger?.focus(); } });
  updateDateDisplay();

  const guestStepper = form?.querySelector('[data-guest-stepper]');
  const guestInput = guestStepper?.querySelector('input[name="guests"]');
  const guestMinus = guestStepper?.querySelector('[data-guest-minus]');
  const guestPlus = guestStepper?.querySelector('[data-guest-plus]');
  const normalizeGuests = () => {
    if (!guestInput) return;
    guestInput.value = guestInput.value.replace(/\D/g,'').replace(/^0+(?=\d)/,'');
  };
  const changeGuests = (delta) => {
    if (!guestInput) return;
    const current = parseInt(guestInput.value || '0', 10) || 0;
    guestInput.value = String(Math.max(1, current + delta));
    guestInput.dispatchEvent(new Event('input', { bubbles:true }));
  };
  guestInput?.addEventListener('input', normalizeGuests);
  guestMinus?.addEventListener('click', () => changeGuests(-1));
  guestPlus?.addEventListener('click', () => changeGuests(1));

  window.addEventListener('kasane:languagechange', () => {
    updateDateDisplay();
    if (datePicker?.classList.contains('is-open')) renderCalendar();
  });

  const autoGrowMessage = () => {
    if (!messageField) return;
    messageField.style.height = 'auto';
    const next = Math.min(Math.max(messageField.scrollHeight, 116), 420);
    messageField.style.height = `${next}px`;
    messageField.style.overflowY = messageField.scrollHeight > 420 ? 'auto' : 'hidden';
  };
  autoGrowMessage();
  messageField?.addEventListener('input', autoGrowMessage);

  const closeCustomSelect = () => {
    customSelect?.classList.remove('is-open');
    selectTrigger?.setAttribute('aria-expanded', 'false');
  };

  const openCustomSelect = () => {
    if (!customSelect) return;
    customSelect.classList.add('is-open');
    selectTrigger?.setAttribute('aria-expanded', 'true');
  };

  const setEventType = (value, { focus = false } = {}) => {
    if (!eventSelect || !selectValue) return;
    eventSelect.value = value;
    selectValue.textContent = tr(value || 'Select event');
    selectOptions.forEach(option => {
      const selected = option.dataset.value === value;
      option.classList.toggle('is-selected', selected);
      option.setAttribute('aria-selected', String(selected));
    });
    eventSelect.closest('label')?.classList.toggle('is-invalid', !value);
    eventSelect.dispatchEvent(new Event('change', { bubbles: true }));
    if (focus) selectTrigger?.focus();
  };

  selectTrigger?.addEventListener('click', () => {
    customSelect.classList.contains('is-open') ? closeCustomSelect() : openCustomSelect();
  });

  selectTrigger?.addEventListener('keydown', (event) => {
    if (['ArrowDown', 'Enter', ' '].includes(event.key) && !customSelect.classList.contains('is-open')) {
      event.preventDefault();
      openCustomSelect();
      const active = selectOptions.find(option => option.dataset.value === eventSelect?.value) || selectOptions[0];
      active?.focus();
    }
  });

  selectOptions.forEach((option, index) => {
    option.addEventListener('click', () => {
      setEventType(option.dataset.value || '', { focus: true });
      closeCustomSelect();
    });
    option.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        selectOptions[(index + 1) % selectOptions.length]?.focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        selectOptions[(index - 1 + selectOptions.length) % selectOptions.length]?.focus();
      } else if (event.key === 'Escape') {
        closeCustomSelect();
        selectTrigger?.focus();
      }
    });
  });

  document.addEventListener('pointerdown', (event) => {
    if (customSelect?.classList.contains('is-open') && !customSelect.contains(event.target)) closeCustomSelect();
  });

  const clearDirection = () => {
    if (briefDirection) briefDirection.value = '';
    if (briefSelection) briefSelection.hidden = true;
  };

  const setDirectionOnBrief = (data) => {
    if (!data) return;
    if (briefDirection) briefDirection.value = data.title;
    if (briefSelectionTitle) briefSelectionTitle.textContent = data.title;
    if (briefSelection) briefSelection.hidden = false;
    if (data.eventType) setEventType(data.eventType);

    if (messageField) {
      const line = currentLanguage === 'id' ? `Referensi arah kreatif: ${tr(data.title)} — ${tr(data.feel)}.` : `Direction reference: ${data.title} — ${data.feel}.`;
      const current = messageField.value.trim();
      if (!current) {
        messageField.value = currentLanguage === 'id' ? `${line}\n\nBagian yang ingin saya pertahankan / ubah dari arah ini: ` : `${line}\n\nWhat I want to keep / change from this direction: `;
      } else if (!current.includes('Direction reference:') && !current.includes('Referensi arah kreatif:')) {
        messageField.value = `${current}\n\n${line}`;
      }
      messageField.closest('label')?.classList.remove('is-invalid');
      autoGrowMessage();
    }
  };
  briefSelectionRemove?.addEventListener('click', clearDirection);

  const clearProduct = () => {
    if (briefProduct) briefProduct.value = '';
    if (productSelection) productSelection.hidden = true;
  };

  const setProductOnBrief = (productName) => {
    if (!productName) return;
    if (briefProduct) briefProduct.value = productName;
    if (productSelectionTitle) productSelectionTitle.textContent = productName;
    if (productSelection) productSelection.hidden = false;
    if (messageField) {
      const line = currentLanguage === 'id' ? `Produk KASANE: ${productName}.` : `KASANE product: ${productName}.`;
      const current = messageField.value.trim();
      if (!current) messageField.value = currentLanguage === 'id' ? `${line}\n\nSaya ingin memasukkan undangan digital personal ini ke event saya.` : `${line}\n\nI would like to include this personalized digital invitation in my event.`;
      else if (!current.includes('KASANE product:') && !current.includes('Produk KASANE:')) messageField.value = `${current}\n\n${line}`;
      autoGrowMessage();
    }
  };

  productSelectionRemove?.addEventListener('click', clearProduct);
  document.querySelectorAll('[data-product-plan]').forEach(button => {
    button.addEventListener('click', () => {
      setProductOnBrief(button.dataset.productPlan || '');
      smoothTo(document.getElementById('contact'));
      setTimeout(() => messageField?.focus(), reduceMotion ? 0 : 650);
    });
  });

  const clearPackage = () => {
    if (briefPackage) briefPackage.value = '';
    if (packageSelection) packageSelection.hidden = true;
  };

  const setPackageOnBrief = (packageName) => {
    if (!packageName) return;
    if (briefPackage) briefPackage.value = packageName;
    if (packageSelectionTitle) packageSelectionTitle.textContent = tr(packageName);
    if (packageSelection) packageSelection.hidden = false;
    if (messageField) {
      const line = currentLanguage === 'id' ? `Preferensi paket: ${tr(packageName)}.` : `Package preference: ${packageName}.`;
      const current = messageField.value.trim();
      if (!current) messageField.value = currentLanguage === 'id' ? `${line}\n\nHal yang sudah saya ketahui tentang event ini: ` : `${line}\n\nWhat I already know about the event: `;
      else if (!current.includes('Package preference:') && !current.includes('Preferensi paket:')) messageField.value = `${current}\n\n${line}`;
      autoGrowMessage();
    }
  };

  packageSelectionRemove?.addEventListener('click', clearPackage);
  window.addEventListener('kasane:languagechange', () => {
    if (eventSelect) setEventType(eventSelect.value);
    if (briefProduct?.value && productSelectionTitle) productSelectionTitle.textContent = briefProduct.value;
    if (briefPackage?.value && packageSelectionTitle) packageSelectionTitle.textContent = tr(briefPackage.value);
  });
  document.querySelectorAll('[data-package-plan]').forEach(button => {
    button.addEventListener('click', () => {
      setPackageOnBrief(button.dataset.packagePlan || '');
      smoothTo(document.getElementById('contact'));
      setTimeout(() => selectTrigger?.focus(), reduceMotion ? 0 : 650);
    });
  });

  const directionData = {
    'quiet-luxury': {
      index: '01 / 04', kicker: 'Wedding direction', title: 'Quiet Luxury',
      image: 'https://images.unsplash.com/photo-1769812343775-85a27e6a076c?auto=format&fit=crop&q=74&w=1200',
      alt: 'Elegant wedding reception table with floral styling',
      text: 'A restrained wedding world where the room feels expensive because every layer is controlled: proportion, texture, lighting, pacing and hospitality. Nothing needs to shout for the event to feel special.',
      best: 'Wedding · engagement dinner · elegant reception',
      feel: 'Warm · tactile · restrained · polished',
      note: 'Use fewer gestures, then make every one of them intentional.',
      eventType: 'Wedding'
    },
    'after-dark': {
      index: '02 / 04', kicker: 'Celebration direction', title: 'After Dark',
      image: 'https://images.unsplash.com/photo-1768594407490-3a7aeb0ec8cc?auto=format&fit=crop&q=74&w=1200',
      alt: 'Wedding reception with hanging lights and greenery',
      text: 'Built around the shift from dinner into a real night out: darker lighting, a stronger music arc, movement, entrance moments and a room that becomes more alive as the program progresses.',
      best: 'Sweet Seventeen · birthday · evening celebration',
      feel: 'Moody · social · kinetic · cinematic',
      note: 'The room should change with the night instead of staying visually flat.',
      eventType: 'Sweet Seventeen'
    },
    'show-moment': {
      index: '03 / 04', kicker: 'Production direction', title: 'Show Moment',
      image: 'assets/images/optimized/production-lights-1280.webp',
      alt: 'Stage production with dramatic event lighting',
      text: 'A production-led direction for events where timing, reveal, lighting and technical cues are part of the experience. The spectacle works because the backstage system is precise.',
      best: 'Brand event · Sweet Seventeen · launch · stage program',
      feel: 'Bold · timed · technical · high-impact',
      note: 'A big moment only feels effortless when every cue underneath it is disciplined.',
      eventType: 'Event Production'
    },
    'golden-hour': {
      index: '04 / 04', kicker: 'Private direction', title: 'Golden Hour',
      image: 'https://images.unsplash.com/photo-1768777270882-9f74939fee50?auto=format&fit=crop&q=74&w=1200',
      alt: 'Wedding table set for an evening celebration',
      text: 'An intimate, hospitality-first direction where the guest list stays close and the details carry more emotional weight: long dinner, softer light, meaningful objects and enough time for the room to breathe.',
      best: 'Private dinner · anniversary · intimate wedding',
      feel: 'Intimate · warm · personal · unhurried',
      note: 'When the guest list is smaller, every touchpoint becomes more visible.',
      eventType: 'Private Celebration'
    }
  };

  const directionModal = document.getElementById('directionModal');
  const directionPanel = directionModal?.querySelector('.direction-modal-panel');
  const directionImage = document.getElementById('directionModalImage');
  const directionIndex = document.getElementById('directionModalIndex');
  const directionKicker = document.getElementById('directionModalKicker');
  const directionTitle = document.getElementById('directionModalTitle');
  const directionText = document.getElementById('directionModalText');
  const directionBest = document.getElementById('directionModalBest');
  const directionFeel = document.getElementById('directionModalFeel');
  const directionNote = document.getElementById('directionModalNote');
  const directionPlan = document.getElementById('directionModalPlan');
  let activeDirectionKey = '';
  let directionReturnFocus = null;

  const openDirectionModal = (key, trigger) => {
    const data = directionData[key];
    if (!data || !directionModal) return;
    activeDirectionKey = key;
    directionModal.dataset.activeDirection = key;
    directionReturnFocus = trigger || document.activeElement;

    if (directionImage) {
      directionImage.style.opacity = '.28';
      setTimeout(() => {
        directionImage.src = data.image;
        directionImage.alt = tr(data.alt);
        directionImage.style.opacity = '1';
      }, 80);
    }
    if (directionIndex) directionIndex.textContent = data.index;
    if (directionKicker) directionKicker.textContent = tr(data.kicker);
    if (directionTitle) directionTitle.textContent = tr(data.title);
    if (directionText) directionText.textContent = tr(data.text);
    if (directionBest) directionBest.textContent = tr(data.best);
    if (directionFeel) directionFeel.textContent = tr(data.feel);
    if (directionNote) directionNote.textContent = tr(data.note);

    directionModal.setAttribute('aria-hidden', 'false');
    body.classList.add('direction-modal-open');
    requestAnimationFrame(() => directionPanel?.focus());
  };

  const closeDirectionModal = () => {
    if (!directionModal || directionModal.getAttribute('aria-hidden') === 'true') return;
    directionModal.setAttribute('aria-hidden', 'true');
    body.classList.remove('direction-modal-open');
    directionReturnFocus?.focus?.();
  };

  document.querySelectorAll('[data-direction]').forEach(trigger => {
    trigger.addEventListener('click', () => openDirectionModal(trigger.dataset.direction, trigger));
  });
  directionModal?.querySelectorAll('[data-direction-close]').forEach(button => button.addEventListener('click', closeDirectionModal));
  window.addEventListener('kasane:languagechange', () => {
    if (activeDirectionKey && directionModal?.getAttribute('aria-hidden') === 'false') openDirectionModal(activeDirectionKey, directionReturnFocus);
  });
  directionPlan?.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    const key = directionModal?.dataset.activeDirection || activeDirectionKey;
    const data = directionData[key];
    if (!data) return;
    setDirectionOnBrief(data);
    closeDirectionModal();
    setTimeout(() => {
      smoothTo(document.getElementById('contact'));
      setTimeout(() => messageField?.focus(), reduceMotion ? 0 : 520);
    }, 40);
  });

  /* Service drawer + carry service type into form */
  const serviceData = {
    wedding: { eventType: 'Wedding', index: '01 / SERVICE', title: 'Wedding Organization', lead: 'From planning architecture to on-the-day control, we keep the wedding personal while the production stays disciplined.', cells: [['Planning', 'Master timeline · scope · budget structure'], ['Creative', 'Event language · styling direction · guest journey'], ['Coordination', 'Venue · vendors · family · rehearsals'], ['Production', 'Run of show · cues · technical handoff']] },
    seventeen: { eventType: 'Sweet Seventeen', index: '02 / SERVICE', title: 'Sweet Seventeen', lead: 'A milestone designed around personality—not a copy-paste theme—with enough production structure to make the night move.', cells: [['Concept', 'Visual world · entrance · program'], ['Experience', 'Guest flow · dinner · party energy'], ['Talent', 'MC · entertainment · performers'], ['Production', 'Stage · lighting · sound · cue sheet']] },
    private: { eventType: 'Private Celebration', index: '03 / SERVICE', title: 'Private Celebrations', lead: 'Smaller guest lists allow every touchpoint to matter more. We shape the atmosphere, flow and details around the people in the room.', cells: [['Occasions', 'Birthdays · anniversaries · dinners'], ['Direction', 'Tablescape · mood · hospitality'], ['Planning', 'Vendor coordination · timeline'], ['On-site', 'Setup · guest flow · show control']] },
    brand: { eventType: 'Corporate / Brand Event', index: '04 / SERVICE', title: 'Brand & Corporate', lead: 'For launches, dinners and gatherings where the environment needs to carry the brand as strongly as the content.', cells: [['Strategy', 'Objective · audience · event narrative'], ['Experience', 'Spatial flow · brand touchpoints'], ['Hospitality', 'Guest handling · dining · gifting'], ['Delivery', 'Vendors · technical · program control']] },
    production: { eventType: 'Event Production', index: '05 / SERVICE', title: 'Event Production', lead: 'The backstage layer: practical, technical and cue-driven support for events that need execution discipline.', cells: [['Technical', 'Stage · sound · lighting · screen'], ['Vendors', 'Sourcing · scope · coordination'], ['Show', 'Run of show · cue calling · rehearsal'], ['Site', 'Load-in · setup · strike · contingency']] }
  };

  const serviceModal = document.getElementById('serviceModal');
  const servicePanel = serviceModal?.querySelector('.service-modal-panel');
  const modalTitle = document.getElementById('serviceModalTitle');
  const modalLead = document.getElementById('serviceModalLead');
  const modalGrid = document.getElementById('serviceModalGrid');
  const modalIndex = document.getElementById('serviceModalIndex');
  const servicePlan = document.querySelector('[data-service-plan]');
  let activeServiceKey = '';
  let serviceReturnFocus = null;

  const closeServiceModal = () => {
    serviceModal?.classList.remove('is-open');
    serviceModal?.setAttribute('aria-hidden', 'true');
    body.classList.remove('modal-open');
    serviceReturnFocus?.focus?.();
  };

  document.querySelectorAll('[data-service]').forEach(btn => {
    btn.addEventListener('click', () => {
      const data = serviceData[btn.dataset.service];
      if (!data || !serviceModal) return;
      activeServiceKey = btn.dataset.service;
      serviceReturnFocus = btn;
      modalIndex.textContent = data.index;
      modalTitle.textContent = tr(data.title);
      modalLead.textContent = tr(data.lead);
      modalGrid.innerHTML = data.cells.map(cell => `<div><span>${tr(cell[0])}</span><strong>${tr(cell[1])}</strong></div>`).join('');
      serviceModal.classList.add('is-open');
      serviceModal.setAttribute('aria-hidden', 'false');
      body.classList.add('modal-open');
      requestAnimationFrame(() => servicePanel?.querySelector('.service-modal-close')?.focus());
    });
  });
  serviceModal?.querySelectorAll('[data-service-close]').forEach(btn => btn.addEventListener('click', closeServiceModal));
  window.addEventListener('kasane:languagechange', () => {
    if (!activeServiceKey || !serviceModal?.classList.contains('is-open')) return;
    const data = serviceData[activeServiceKey];
    if (!data) return;
    modalTitle.textContent = tr(data.title);
    modalLead.textContent = tr(data.lead);
    modalGrid.innerHTML = data.cells.map(cell => `<div><span>${tr(cell[0])}</span><strong>${tr(cell[1])}</strong></div>`).join('');
  });
  servicePlan?.addEventListener('click', () => {
    const data = serviceData[activeServiceKey];
    if (data) {
      setEventType(data.eventType);
      if (messageField && !messageField.value.trim()) {
        messageField.value = currentLanguage === 'id' ? `Saya tertarik dengan layanan ${tr(data.title)} dari KASANE.\n\nHal yang sudah saya ketahui tentang event ini: ` : `I’m interested in KASANE’s ${data.title} service.\n\nWhat I already know about the event: `;
        autoGrowMessage();
      }
    }
    closeServiceModal();
    setTimeout(() => smoothTo(document.getElementById('contact')), 70);
  });

  /* Modal focus containment + global Escape behavior */
  const trapTab = (event, panel) => {
    const focusable = [...panel.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')]
      .filter(el => !el.disabled && el.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (directionModal?.getAttribute('aria-hidden') === 'false') closeDirectionModal();
      else if (serviceModal?.classList.contains('is-open')) closeServiceModal();
      else if (customSelect?.classList.contains('is-open')) closeCustomSelect();
      else setMenu(false);
    }
    if (event.key === 'Tab') {
      if (directionModal?.getAttribute('aria-hidden') === 'false' && directionPanel) trapTab(event, directionPanel);
      else if (serviceModal?.classList.contains('is-open') && servicePanel) trapTab(event, servicePanel);
    }
  });

  /* Contact preference: require only the channel the visitor actually chose. */
  const phoneInput = form?.querySelector('[name="phone"]');
  const emailInput = form?.querySelector('[name="email"]');
  const phoneMark = form?.querySelector('[data-required-mark="phone"]');
  const emailMark = form?.querySelector('[data-required-mark="email"]');
  const contactRadios = [...(form?.querySelectorAll('[name="preferred_contact"]') || [])];
  const formErrors = {
    name: document.getElementById('nameError'),
    phone: document.getElementById('phoneError'),
    email: document.getElementById('emailError'),
    event: document.getElementById('eventError'),
    message: document.getElementById('messageError')
  };
  const submitButton = form?.querySelector('button[type="submit"]');
  const submitButtonLabel = submitButton?.innerHTML || '';

  const setFieldError = (field, message = '') => {
    if (!field) return;
    const label = field.closest('label');
    label?.classList.toggle('is-invalid', Boolean(message));
    field.setAttribute('aria-invalid', message ? 'true' : 'false');
    const key = field.name;
    if (formErrors[key]) formErrors[key].textContent = message;
  };

  const clearFieldError = (field) => setFieldError(field, '');

  const syncContactRequirements = () => {
    if (!form) return;
    const selected = form.querySelector('[name="preferred_contact"]:checked')?.value || 'WhatsApp';
    const needsEmail = selected === 'Email';
    const needsPhone = ['WhatsApp', 'Call', 'SMS'].includes(selected);

    if (phoneInput) {
      phoneInput.required = needsPhone;
      phoneInput.setAttribute('aria-required', needsPhone ? 'true' : 'false');
      if (!needsPhone) clearFieldError(phoneInput);
    }
    if (emailInput) {
      emailInput.required = needsEmail;
      emailInput.setAttribute('aria-required', needsEmail ? 'true' : 'false');
      if (!needsEmail) clearFieldError(emailInput);
    }
    if (phoneMark) phoneMark.textContent = needsPhone ? '*' : '';
    if (emailMark) emailMark.textContent = needsEmail ? '*' : '';
  };

  contactRadios.forEach(radio => radio.addEventListener('change', syncContactRequirements));
  syncContactRequirements();

  /* Cloudflare Turnstile: loaded only when a public site key is configured. */
  const captchaSlot = document.getElementById('captchaSlot');
  const captchaError = document.getElementById('captchaError');
  let captchaWidgetId = null;
  let captchaToken = '';

  const resetCaptcha = () => {
    captchaToken = '';
    if (window.turnstile && captchaWidgetId !== null) {
      try { window.turnstile.reset(captchaWidgetId); } catch (_) {}
    }
  };

  const initTurnstile = () => {
    if (!TURNSTILE_SITE_KEY || !captchaSlot) return;
    captchaSlot.hidden = false;
    const render = () => {
      if (!window.turnstile || captchaWidgetId !== null) return;
      captchaWidgetId = window.turnstile.render('#turnstileWidget', {
        sitekey: TURNSTILE_SITE_KEY,
        action: TURNSTILE_ACTION,
        theme: 'dark',
        size: 'flexible',
        language: 'auto',
        callback: token => { captchaToken = token; if (captchaError) captchaError.textContent = ''; },
        'expired-callback': () => { captchaToken = ''; },
        'error-callback': () => { captchaToken = ''; if (captchaError) captchaError.textContent = tr('Verification could not load. Please try again.'); }
      });
    };
    if (window.turnstile) return render();
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.onload = render;
    document.head.appendChild(script);
  };
  initTurnstile();

  /* Contact: production endpoint when configured; safe email handoff otherwise. */
  const buildBrief = (data, preferredContact) => {
    const eventType = data.get('event') || 'Event';
    const direction = data.get('direction') || '';
    const productName = data.get('product') || '';
    const packageName = data.get('package') || '';
    const openLabel = currentLanguage === 'id' ? 'Belum dipilih' : 'Open / not selected yet';
    const payload = {
      version: 'phase5',
      language: currentLanguage,
      submittedAt: new Date().toISOString(),
      name: String(data.get('name') || '').trim(),
      phone: String(data.get('phone') || '').trim(),
      email: String(data.get('email') || '').trim(),
      preferredContact,
      eventType,
      product: productName,
      package: packageName,
      direction,
      city: String(data.get('city') || '').trim(),
      date: String(data.get('date') || '').trim(),
      guests: String(data.get('guests') || '').trim(),
      message: String(data.get('message') || '').trim(),
      page: location.href,
      submissionId: (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`),
      captchaToken,
      website: String(data.get('website') || '').trim()
    };
    const lines = currentLanguage === 'id' ? [
      'Halo KASANE COLLECTIVE','','Saya ingin memulai brief event.','',
      `Nama: ${payload.name}`,
      `WhatsApp / Telepon: ${payload.phone}`,
      `Email: ${payload.email || '-'}`,
      `Kontak pilihan: ${preferredContact === 'Call' ? 'Telepon' : preferredContact}`,
      `Jenis event: ${tr(eventType)}`,
      `Produk KASANE: ${productName || openLabel}`,
      `Paket / scope: ${packageName ? tr(packageName) : openLabel}`,
      `Arah kreatif: ${direction ? tr(direction) : openLabel}`,
      `Kota / Venue: ${payload.city || 'TBD'}`,
      `Tanggal event: ${payload.date || 'TBD'}`,
      `Perkiraan tamu: ${payload.guests || 'TBD'}`,'','Brief:',payload.message
    ] : [
      'Hello KASANE COLLECTIVE','','I would like to start an event brief.','',
      `Name: ${payload.name}`,
      `WhatsApp / Phone: ${payload.phone}`,
      `Email: ${payload.email || '-'}`,
      `Preferred contact: ${preferredContact}`,
      `Event type: ${eventType}`,
      `KASANE product: ${productName || openLabel}`,
      `Package / scope: ${packageName || openLabel}`,
      `Creative direction: ${direction || openLabel}`,
      `City / Venue: ${payload.city || 'TBD'}`,
      `Event date: ${payload.date || 'TBD'}`,
      `Estimated guests: ${payload.guests || 'TBD'}`,'','Brief:',payload.message
    ];
    return { payload, lines, eventType };
  };

  const openEmailBrief = ({ lines, eventType }) => {
    const subject = currentLanguage === 'id' ? `KASANE Brief Event — ${tr(eventType)}` : `KASANE Event Brief — ${eventType}`;
    const href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`;
    window.location.href = href;
  };

  const validateBrief = (preferredContact) => {
    if (!form) return null;
    const nameInput = form.querySelector('[name="name"]');
    const messageInput = form.querySelector('[name="message"]');
    const needsPhone = ['WhatsApp','Call','SMS'].includes(preferredContact);
    const needsEmail = preferredContact === 'Email';
    const checks = [
      [nameInput, String(nameInput?.value || '').trim() ? '' : tr('Required field.')],
      [phoneInput, !needsPhone || String(phoneInput?.value || '').trim() ? '' : tr('Please enter a phone number for this contact method.')],
      [emailInput, !needsEmail ? '' : (!String(emailInput?.value || '').trim() || !emailInput?.validity.valid ? tr('Please enter a valid email address.') : '')],
      [eventSelect, String(eventSelect?.value || '').trim() ? '' : tr('Please select an event type.')],
      [messageInput, String(messageInput?.value || '').trim() ? '' : tr('Please tell us a little about the event.')]
    ];
    checks.forEach(([field,message]) => setFieldError(field,message));
    return checks.find(([,message]) => message)?.[0] || null;
  };

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    syncContactRequirements();
    const data = new FormData(form);
    const preferredContact = data.get('preferred_contact') || 'WhatsApp';
    const firstInvalid = validateBrief(preferredContact);
    if (!firstInvalid && TURNSTILE_SITE_KEY && !captchaToken) {
      if (captchaError) captchaError.textContent = tr('Please complete the verification.');
      if (status) status.textContent = tr('Please complete the verification before sending your brief.');
      return;
    }
    if (firstInvalid) {
      if (firstInvalid === eventSelect) {
        openCustomSelect();
        selectTrigger?.focus();
      } else firstInvalid.focus();
      if (status) status.textContent = tr('Please complete the required fields before preparing the brief.');
      return;
    }

    const brief = buildBrief(data, preferredContact);
    if (!BRIEF_ENDPOINT) {
      if (status) status.textContent = tr('Opening your message now.');
      openEmailBrief(brief);
      return;
    }

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.setAttribute('aria-busy','true');
      submitButton.textContent = tr('Sending your brief…');
    }
    if (status) status.textContent = tr('Sending your brief…');

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(BRIEF_ENDPOINT, {
        method: 'POST',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        body: JSON.stringify(brief.payload),
        signal: controller.signal
      });
      let result = {};
      try { result = await response.json(); } catch (_) {}
      if (!response.ok) {
        resetCaptcha();
        if ([400,403,429].includes(response.status)) {
          if (status) status.textContent = result.message || tr('Please review the form and try again.');
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      const ref = result.reference || result.referenceId || '';
      if (status) status.textContent = `${tr('Brief received.')} ${ref ? `#${ref} · ` : ''}${tr('We’ll contact you through your preferred channel.')}`;
      form.classList.add('is-submitted');
      resetCaptcha();
    } catch (error) {
      console.warn('KASANE brief endpoint unavailable; falling back to email handoff.', error);
      resetCaptcha();
      if (status) status.textContent = tr('We could not send the brief online. Opening your email instead.');
      openEmailBrief(brief);
    } finally {
      clearTimeout(timer);
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.removeAttribute('aria-busy');
        submitButton.innerHTML = submitButtonLabel;
      }
    }
  });

  form?.addEventListener('input', (event) => {
    const field = event.target;
    if (!field?.name) return;
    const value = String(field.value || '').trim();
    if (value && (field.type !== 'email' || field.validity.valid)) clearFieldError(field);
  });

  document.getElementById('year').textContent = new Date().getFullYear();
})();
