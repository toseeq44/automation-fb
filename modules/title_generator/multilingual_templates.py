"""
Multilingual Title Templates for Facebook & TikTok
Content-aware title generation in multiple languages
Optimized for viral engagement on social media platforms
"""

from typing import Dict, List
from modules.logging.logger import get_logger

logger = get_logger(__name__)


class MultilingualTemplates:
    """
    Multilingual title templates optimized for Facebook and TikTok

    Supported languages:
    - English (en)
    - Portuguese/Brazilian (pt)
    - French (fr)
    - Spanish (es)
    - Urdu (ur)
    - Hindi (hi)
    - Arabic (ar)
    """

    # Platform-specific character limits
    PLATFORM_LIMITS = {
        'facebook': 255,  # Facebook post title limit
        'tiktok': 150,    # TikTok caption optimal length
        'instagram': 125, # Instagram caption optimal (first line)
        'youtube': 100    # YouTube title limit
    }

    # Language-specific templates
    TEMPLATES = {
        'en': {
            # COOKING NICHE
            'cooking': {
                'speed': [
                    "{FOOD} in Just {TIME} | Quick Recipe",
                    "Making Perfect {FOOD} in {TIME}",
                    "{TIME} {FOOD} Recipe You Must Try",
                    "Fast & Easy {FOOD} in {TIME}",
                    "How to Make {FOOD} in {TIME}"
                ],
                'tutorial': [
                    "Perfect {FOOD} Recipe | Step by Step",
                    "How I Make {FOOD} Like a Pro",
                    "The Secret to Perfect {FOOD}",
                    "{FOOD} Recipe Everyone Loves",
                    "Easy {FOOD} Recipe for Beginners"
                ],
                'viral': [
                    "This {FOOD} Recipe Changed My Life",
                    "You Won't Believe This {FOOD} Trick",
                    "I Tried Making {FOOD} and This Happened",
                    "The Best {FOOD} I've Ever Made",
                    "Everyone Needs This {FOOD} Recipe"
                ]
            },

            # GAMING NICHE
            'gaming': {
                'gameplay': [
                    "{GAME} in {TIME} | Insane Gameplay",
                    "Playing {GAME} Like a Pro",
                    "{GAME} Gameplay Highlights",
                    "Epic {GAME} Moments",
                    "{GAME} Victory in {TIME}"
                ],
                'challenge': [
                    "{GAME} {TIME} Speed Challenge",
                    "Can I Beat {GAME} in {TIME}?",
                    "Impossible {GAME} Challenge",
                    "{GAME} No Death Run",
                    "Trying {GAME} Hardest Level"
                ]
            },

            # REVIEW NICHE
            'review': {
                'product': [
                    "{PRODUCT} Review | Is It Worth It?",
                    "Honest {PRODUCT} Review After {TIME}",
                    "I Tested {PRODUCT} for {TIME}",
                    "{PRODUCT} Unboxing & First Impressions",
                    "Should You Buy {PRODUCT}?"
                ],
                'comparison': [
                    "{PRODUCT} vs {ALT} | Which is Better?",
                    "Don't Buy {PRODUCT} Until You Watch This",
                    "{PRODUCT} Truth Nobody Tells You",
                    "Is {PRODUCT} Actually Good?",
                    "{PRODUCT} After {TIME} | Honest Opinion"
                ]
            },

            # TUTORIAL NICHE
            'tutorial': {
                'how_to': [
                    "How to {ACTION} in {TIME}",
                    "{TOPIC} Tutorial for Beginners",
                    "Learn {TOPIC} in {TIME}",
                    "Easy Way to {ACTION}",
                    "{TOPIC} Made Simple"
                ],
                'guide': [
                    "Complete {TOPIC} Guide",
                    "Master {TOPIC} Step by Step",
                    "{TOPIC} Like a Pro",
                    "Ultimate {TOPIC} Tutorial",
                    "{TOPIC} Explained Simply"
                ]
            },

            # VLOG NICHE
            'vlog': {
                'daily': [
                    "A Day in My Life | {TOPIC}",
                    "What I Did Today | {TOPIC}",
                    "My {TIME} Routine",
                    "Behind the Scenes | {TOPIC}",
                    "Real Talk About {TOPIC}"
                ],
                'travel': [
                    "Exploring {PLACE} in {TIME}",
                    "{PLACE} Travel Vlog",
                    "Best of {PLACE} | Must Visit",
                    "My {PLACE} Adventure",
                    "{PLACE} You've Never Seen"
                ]
            },

            # FITNESS NICHE
            'fitness': {
                'workout': [
                    "{TIME} {EXERCISE} Workout",
                    "Full Body Workout in {TIME}",
                    "{EXERCISE} Challenge",
                    "Get Fit in {TIME} | {EXERCISE}",
                    "{EXERCISE} Routine That Works"
                ],
                'transformation': [
                    "My {TIME} Fitness Transformation",
                    "How I Lost Weight in {TIME}",
                    "{TIME} Body Challenge Results",
                    "Fitness Journey | {TIME} Update",
                    "Before & After {TIME}"
                ]
            }
        },

        'pt': {  # PORTUGUESE (BRAZILIAN)
            'cooking': {
                'speed': [
                    "{FOOD} em Apenas {TIME} | Receita Rápida",
                    "Fazendo {FOOD} Perfeito em {TIME}",
                    "Receita de {FOOD} em {TIME}",
                    "{FOOD} Rápido e Fácil em {TIME}",
                    "Como Fazer {FOOD} em {TIME}"
                ],
                'tutorial': [
                    "Receita Perfeita de {FOOD} | Passo a Passo",
                    "Como Eu Faço {FOOD} Como um Chef",
                    "O Segredo do {FOOD} Perfeito",
                    "Receita de {FOOD} Que Todos Amam",
                    "Receita Fácil de {FOOD}"
                ],
                'viral': [
                    "Esta Receita de {FOOD} Mudou Minha Vida",
                    "Você Não Vai Acreditar Neste Truque de {FOOD}",
                    "Fiz {FOOD} e Isso Aconteceu",
                    "O Melhor {FOOD} Que Já Fiz",
                    "Todo Mundo Precisa Desta Receita de {FOOD}"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{GAME} em {TIME} | Gameplay Insano",
                    "Jogando {GAME} Como um Pro",
                    "Melhores Momentos de {GAME}",
                    "Momentos Épicos de {GAME}",
                    "Vitória em {GAME} em {TIME}"
                ],
                'challenge': [
                    "Desafio {GAME} em {TIME}",
                    "Consigo Zerar {GAME} em {TIME}?",
                    "Desafio Impossível de {GAME}",
                    "{GAME} Sem Morrer",
                    "Tentando a Fase Mais Difícil de {GAME}"
                ]
            },
            'review': {
                'product': [
                    "Review {PRODUCT} | Vale a Pena?",
                    "Review Honesto do {PRODUCT} Após {TIME}",
                    "Testei {PRODUCT} por {TIME}",
                    "Unboxing {PRODUCT} e Primeiras Impressões",
                    "Você Deve Comprar {PRODUCT}?"
                ]
            },
            'tutorial': {
                'how_to': [
                    "Como {ACTION} em {TIME}",
                    "Tutorial de {TOPIC} para Iniciantes",
                    "Aprenda {TOPIC} em {TIME}",
                    "Jeito Fácil de {ACTION}",
                    "{TOPIC} Simplificado"
                ]
            },
            'vlog': {
                'daily': [
                    "Um Dia na Minha Vida | {TOPIC}",
                    "O Que Fiz Hoje | {TOPIC}",
                    "Minha Rotina de {TIME}",
                    "Nos Bastidores | {TOPIC}",
                    "Papo Reto Sobre {TOPIC}"
                ]
            },
            'fitness': {
                'workout': [
                    "Treino de {EXERCISE} de {TIME}",
                    "Treino Completo em {TIME}",
                    "Desafio de {EXERCISE}",
                    "Fique em Forma em {TIME}",
                    "Rotina de {EXERCISE} Que Funciona"
                ]
            }
        },

        'fr': {  # FRENCH
            'cooking': {
                'speed': [
                    "{FOOD} en Seulement {TIME} | Recette Rapide",
                    "Faire un {FOOD} Parfait en {TIME}",
                    "Recette de {FOOD} en {TIME}",
                    "{FOOD} Rapide et Facile en {TIME}",
                    "Comment Faire {FOOD} en {TIME}"
                ],
                'tutorial': [
                    "Recette Parfaite de {FOOD} | Étape par Étape",
                    "Comment Je Fais {FOOD} Comme un Chef",
                    "Le Secret du {FOOD} Parfait",
                    "Recette de {FOOD} Que Tout le Monde Aime",
                    "Recette Facile de {FOOD}"
                ],
                'viral': [
                    "Cette Recette de {FOOD} a Changé Ma Vie",
                    "Vous N'allez Pas Croire Cette Astuce de {FOOD}",
                    "J'ai Fait {FOOD} et Voici Ce Qui S'est Passé",
                    "Le Meilleur {FOOD} Que J'ai Jamais Fait",
                    "Tout le Monde a Besoin de Cette Recette de {FOOD}"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{GAME} en {TIME} | Gameplay Fou",
                    "Jouer à {GAME} Comme un Pro",
                    "Meilleurs Moments de {GAME}",
                    "Moments Épiques de {GAME}",
                    "Victoire {GAME} en {TIME}"
                ]
            },
            'review': {
                'product': [
                    "Test {PRODUCT} | Ça Vaut le Coup?",
                    "Test Honnête du {PRODUCT} Après {TIME}",
                    "J'ai Testé {PRODUCT} Pendant {TIME}",
                    "Déballage {PRODUCT} et Premières Impressions",
                    "Faut-il Acheter {PRODUCT}?"
                ]
            },
            'tutorial': {
                'how_to': [
                    "Comment {ACTION} en {TIME}",
                    "Tutoriel {TOPIC} pour Débutants",
                    "Apprendre {TOPIC} en {TIME}",
                    "Façon Facile de {ACTION}",
                    "{TOPIC} Simplifié"
                ]
            },
            'vlog': {
                'daily': [
                    "Une Journée dans Ma Vie | {TOPIC}",
                    "Ce Que J'ai Fait Aujourd'hui | {TOPIC}",
                    "Ma Routine de {TIME}",
                    "Les Coulisses | {TOPIC}",
                    "Parlons Franchement de {TOPIC}"
                ]
            },
            'fitness': {
                'workout': [
                    "Entraînement {EXERCISE} de {TIME}",
                    "Entraînement Complet en {TIME}",
                    "Défi {EXERCISE}",
                    "Soyez en Forme en {TIME}",
                    "Routine {EXERCISE} Qui Marche"
                ]
            }
        },

        'es': {  # SPANISH
            'cooking': {
                'speed': [
                    "{FOOD} en Solo {TIME} | Receta Rápida",
                    "Haciendo {FOOD} Perfecto en {TIME}",
                    "Receta de {FOOD} en {TIME}",
                    "{FOOD} Rápido y Fácil en {TIME}",
                    "Cómo Hacer {FOOD} en {TIME}"
                ],
                'tutorial': [
                    "Receta Perfecta de {FOOD} | Paso a Paso",
                    "Cómo Hago {FOOD} Como un Chef",
                    "El Secreto del {FOOD} Perfecto",
                    "Receta de {FOOD} Que Todos Aman",
                    "Receta Fácil de {FOOD}"
                ],
                'viral': [
                    "Esta Receta de {FOOD} Cambió Mi Vida",
                    "No Vas a Creer Este Truco de {FOOD}",
                    "Hice {FOOD} y Esto Pasó",
                    "El Mejor {FOOD} Que He Hecho",
                    "Todos Necesitan Esta Receta de {FOOD}"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{GAME} en {TIME} | Gameplay Increíble",
                    "Jugando {GAME} Como un Pro",
                    "Mejores Momentos de {GAME}",
                    "Momentos Épicos de {GAME}",
                    "Victoria en {GAME} en {TIME}"
                ]
            },
            'review': {
                'product': [
                    "Review {PRODUCT} | ¿Vale la Pena?",
                    "Review Honesto del {PRODUCT} Después de {TIME}",
                    "Probé {PRODUCT} por {TIME}",
                    "Unboxing {PRODUCT} y Primeras Impresiones",
                    "¿Deberías Comprar {PRODUCT}?"
                ]
            },
            'tutorial': {
                'how_to': [
                    "Cómo {ACTION} en {TIME}",
                    "Tutorial de {TOPIC} para Principiantes",
                    "Aprende {TOPIC} en {TIME}",
                    "Forma Fácil de {ACTION}",
                    "{TOPIC} Simplificado"
                ]
            },
            'vlog': {
                'daily': [
                    "Un Día en Mi Vida | {TOPIC}",
                    "Lo Que Hice Hoy | {TOPIC}",
                    "Mi Rutina de {TIME}",
                    "Detrás de Cámaras | {TOPIC}",
                    "Hablemos de {TOPIC}"
                ]
            },
            'fitness': {
                'workout': [
                    "Entrenamiento de {EXERCISE} de {TIME}",
                    "Entrenamiento Completo en {TIME}",
                    "Desafío de {EXERCISE}",
                    "Ponte en Forma en {TIME}",
                    "Rutina de {EXERCISE} Que Funciona"
                ]
            }
        },

        'ur': {  # URDU
            'cooking': {
                'speed': [
                    "صرف {TIME} میں {FOOD} | جلدی ریسیپی",
                    "{TIME} میں کامل {FOOD} بنائیں",
                    "{FOOD} کی آسان ریسیپی {TIME} میں",
                    "تیز اور آسان {FOOD} {TIME} میں",
                    "{TIME} میں {FOOD} کیسے بنائیں"
                ],
                'tutorial': [
                    "{FOOD} کی بہترین ریسیپی | قدم بہ قدم",
                    "میں {FOOD} کیسے بناتا ہوں",
                    "{FOOD} کا راز",
                    "{FOOD} کی آسان ریسیپی",
                    "ہر کوئی {FOOD} کی یہ ریسیپی پسند کرتا ہے"
                ],
                'viral': [
                    "اس {FOOD} نے میری زندگی بدل دی",
                    "آپ یقین نہیں کریں گے یہ {FOOD} ٹرک",
                    "میں نے {FOOD} بنایا اور یہ ہوا",
                    "سب سے بہترین {FOOD} جو میں نے بنایا",
                    "ہر کسی کو یہ {FOOD} ریسیپی چاہیے"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{TIME} میں {GAME} | شاندار گیم پلے",
                    "{GAME} پرو کی طرح کھیلنا",
                    "{GAME} کے بہترین لمحات",
                    "{GAME} کے دلچسپ لمحات",
                    "{TIME} میں {GAME} جیت"
                ]
            },
            'review': {
                'product': [
                    "{PRODUCT} ریویو | کیا یہ قابل ہے؟",
                    "{TIME} بعد ایماندار {PRODUCT} ریویو",
                    "میں نے {TIME} تک {PRODUCT} ٹیسٹ کیا",
                    "{PRODUCT} انباکسنگ اور پہلا تاثر",
                    "کیا آپ {PRODUCT} خریدیں؟"
                ]
            },
            'tutorial': {
                'how_to': [
                    "{TIME} میں {ACTION} کیسے کریں",
                    "شروع کرنے والوں کے لیے {TOPIC} ٹیوٹوریل",
                    "{TIME} میں {TOPIC} سیکھیں",
                    "{ACTION} کا آسان طریقہ",
                    "{TOPIC} آسان بنایا"
                ]
            },
            'vlog': {
                'daily': [
                    "میری زندگی کا ایک دن | {TOPIC}",
                    "آج میں نے کیا کیا | {TOPIC}",
                    "میرا {TIME} روٹین",
                    "پردے کے پیچھے | {TOPIC}",
                    "{TOPIC} کے بارے میں حقیقی بات"
                ]
            },
            'fitness': {
                'workout': [
                    "{TIME} {EXERCISE} ورزش",
                    "{TIME} میں مکمل ورزش",
                    "{EXERCISE} چیلنج",
                    "{TIME} میں فٹ ہو جائیں",
                    "{EXERCISE} روٹین جو کام کرتا ہے"
                ]
            }
        },

        'hi': {  # HINDI
            'cooking': {
                'speed': [
                    "सिर्फ {TIME} में {FOOD} | जल्दी रेसिपी",
                    "{TIME} में परफेक्ट {FOOD} बनाएं",
                    "{TIME} में {FOOD} रेसिपी",
                    "{TIME} में आसान {FOOD}",
                    "{TIME} में {FOOD} कैसे बनाएं"
                ],
                'tutorial': [
                    "{FOOD} की बेस्ट रेसिपी | स्टेप बाय स्टेप",
                    "मैं {FOOD} कैसे बनाता हूं",
                    "{FOOD} का राज",
                    "{FOOD} की आसान रेसिपी",
                    "सभी को {FOOD} की यह रेसिपी पसंद है"
                ],
                'viral': [
                    "इस {FOOD} ने मेरी जिंदगी बदल दी",
                    "आप इस {FOOD} ट्रिक पर यकीन नहीं करेंगे",
                    "मैंने {FOOD} बनाया और यह हुआ",
                    "सबसे बेस्ट {FOOD} जो मैंने बनाया",
                    "सभी को यह {FOOD} रेसिपी चाहिए"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{TIME} में {GAME} | धमाकेदार गेमप्ले",
                    "{GAME} प्रो की तरह खेलना",
                    "{GAME} के बेस्ट मोमेंट्स",
                    "{GAME} के शानदार पल",
                    "{TIME} में {GAME} जीत"
                ]
            },
            'review': {
                'product': [
                    "{PRODUCT} रिव्यू | क्या यह लायक है?",
                    "{TIME} बाद ईमानदार {PRODUCT} रिव्यू",
                    "मैंने {TIME} तक {PRODUCT} टेस्ट किया",
                    "{PRODUCT} अनबॉक्सिंग और पहली छाप",
                    "क्या आप {PRODUCT} खरीदें?"
                ]
            },
            'tutorial': {
                'how_to': [
                    "{TIME} में {ACTION} कैसे करें",
                    "शुरुआती लोगों के लिए {TOPIC} ट्यूटोरियल",
                    "{TIME} में {TOPIC} सीखें",
                    "{ACTION} का आसान तरीका",
                    "{TOPIC} आसान बनाया"
                ]
            },
            'vlog': {
                'daily': [
                    "मेरी जिंदगी का एक दिन | {TOPIC}",
                    "आज मैंने क्या किया | {TOPIC}",
                    "मेरा {TIME} रूटीन",
                    "पर्दे के पीछे | {TOPIC}",
                    "{TOPIC} के बारे में सच्ची बात"
                ]
            },
            'fitness': {
                'workout': [
                    "{TIME} {EXERCISE} वर्कआउट",
                    "{TIME} में पूरा वर्कआउट",
                    "{EXERCISE} चैलेंज",
                    "{TIME} में फिट हो जाएं",
                    "{EXERCISE} रूटीन जो काम करता है"
                ]
            }
        },

        'ar': {  # ARABIC
            'cooking': {
                'speed': [
                    "{FOOD} في {TIME} فقط | وصفة سريعة",
                    "صنع {FOOD} مثالي في {TIME}",
                    "وصفة {FOOD} في {TIME}",
                    "{FOOD} سريع وسهل في {TIME}",
                    "كيفية صنع {FOOD} في {TIME}"
                ],
                'tutorial': [
                    "وصفة {FOOD} مثالية | خطوة بخطوة",
                    "كيف أصنع {FOOD} مثل الطاهي",
                    "سر {FOOD} المثالي",
                    "وصفة {FOOD} يحبها الجميع",
                    "وصفة {FOOD} سهلة"
                ]
            },
            'gaming': {
                'gameplay': [
                    "{GAME} في {TIME} | لعب رائع",
                    "لعب {GAME} مثل المحترفين",
                    "أفضل لحظات {GAME}",
                    "لحظات {GAME} الملحمية",
                    "فوز {GAME} في {TIME}"
                ]
            },
            'review': {
                'product': [
                    "مراجعة {PRODUCT} | هل يستحق؟",
                    "مراجعة صادقة لـ {PRODUCT} بعد {TIME}",
                    "اختبرت {PRODUCT} لمدة {TIME}",
                    "فتح صندوق {PRODUCT} والانطباعات الأولى",
                    "هل يجب شراء {PRODUCT}؟"
                ]
            },
            'tutorial': {
                'how_to': [
                    "كيفية {ACTION} في {TIME}",
                    "تعليم {TOPIC} للمبتدئين",
                    "تعلم {TOPIC} في {TIME}",
                    "الطريقة السهلة لـ {ACTION}",
                    "{TOPIC} مبسط"
                ]
            }
        }
    }

    # Facebook/TikTok viral hooks (language-independent patterns)
    VIRAL_HOOKS = {
        'facebook': {
            'en': [
                "This {TOPIC} will blow your mind",
                "Everyone is talking about this {TOPIC}",
                "You need to see this {TOPIC}",
                "This {TOPIC} went viral for a reason",
                "Watch till the end"
            ],
            'pt': [
                "Este {TOPIC} vai surpreender você",
                "Todo mundo está falando sobre este {TOPIC}",
                "Você precisa ver este {TOPIC}",
                "Este {TOPIC} viralizou por um motivo",
                "Assista até o final"
            ],
            'fr': [
                "Ce {TOPIC} va vous épater",
                "Tout le monde parle de ce {TOPIC}",
                "Vous devez voir ce {TOPIC}",
                "Ce {TOPIC} est devenu viral pour une raison",
                "Regardez jusqu'à la fin"
            ],
            'es': [
                "Este {TOPIC} te va a sorprender",
                "Todo el mundo habla de este {TOPIC}",
                "Necesitas ver este {TOPIC}",
                "Este {TOPIC} se volvió viral por una razón",
                "Mira hasta el final"
            ],
            'ur': [
                "یہ {TOPIC} آپ کو حیران کر دے گا",
                "ہر کوئی اس {TOPIC} کے بارے میں بات کر رہا ہے",
                "آپ کو یہ {TOPIC} دیکھنا چاہیے",
                "یہ {TOPIC} وائرل ہوا ایک وجہ سے",
                "آخر تک دیکھیں"
            ],
            'hi': [
                "यह {TOPIC} आपको हैरान कर देगा",
                "सभी इस {TOPIC} के बारे में बात कर रहे हैं",
                "आपको यह {TOPIC} देखना चाहिए",
                "यह {TOPIC} वायरल हुआ एक कारण से",
                "अंत तक देखें"
            ]
        },
        'tiktok': {
            'en': [
                "{TOPIC} hack you didn't know",
                "POV: {TOPIC}",
                "{TOPIC} that actually works",
                "Try this {TOPIC}",
                "{TOPIC} part {NUMBER}"
            ],
            'pt': [
                "Truque de {TOPIC} que você não sabia",
                "POV: {TOPIC}",
                "{TOPIC} que realmente funciona",
                "Experimente este {TOPIC}",
                "{TOPIC} parte {NUMBER}"
            ],
            'fr': [
                "Astuce {TOPIC} que vous ne connaissiez pas",
                "POV: {TOPIC}",
                "{TOPIC} qui fonctionne vraiment",
                "Essayez ce {TOPIC}",
                "{TOPIC} partie {NUMBER}"
            ],
            'es': [
                "Truco de {TOPIC} que no conocías",
                "POV: {TOPIC}",
                "{TOPIC} que realmente funciona",
                "Prueba este {TOPIC}",
                "{TOPIC} parte {NUMBER}"
            ],
            'ur': [
                "{TOPIC} ہیک جو آپ نہیں جانتے تھے",
                "POV: {TOPIC}",
                "{TOPIC} جو واقعی کام کرتا ہے",
                "یہ {TOPIC} آزمائیں",
                "{TOPIC} حصہ {NUMBER}"
            ],
            'hi': [
                "{TOPIC} हैक जो आप नहीं जानते थे",
                "POV: {TOPIC}",
                "{TOPIC} जो वास्तव में काम करता है",
                "यह {TOPIC} आज़माएं",
                "{TOPIC} भाग {NUMBER}"
            ]
        }
    }

    def __init__(self):
        """Initialize multilingual templates"""
        self.supported_languages = list(self.TEMPLATES.keys())
        logger.info(f"Multilingual templates loaded: {', '.join(self.supported_languages)}")

    def get_templates(
        self,
        language: str,
        niche: str,
        template_type: str = 'speed',
        platform: str = 'facebook'
    ) -> List[str]:
        """
        Get title templates for specific language, niche, and type

        Args:
            language: ISO language code ('en', 'pt', 'fr', etc.)
            niche: Video niche ('cooking', 'gaming', 'review', etc.)
            template_type: Template category ('speed', 'tutorial', 'viral', etc.)
            platform: Target platform ('facebook', 'tiktok', 'instagram')

        Returns:
            List of title templates
        """
        # Default to English if language not supported
        if language not in self.TEMPLATES:
            logger.warning(f"Language '{language}' not supported, using English")
            language = 'en'

        # Get language templates
        lang_templates = self.TEMPLATES[language]

        # Get niche templates (default to 'cooking' if not found)
        niche_templates = lang_templates.get(niche, lang_templates.get('cooking', {}))

        # Get specific template type
        templates = niche_templates.get(template_type, [])

        # If no templates found, use first available type
        if not templates:
            templates = list(niche_templates.values())[0] if niche_templates else []

        return templates

    def get_viral_hooks(self, language: str, platform: str = 'facebook') -> List[str]:
        """
        Get platform-specific viral hooks

        Args:
            language: ISO language code
            platform: 'facebook' or 'tiktok'

        Returns:
            List of viral hook templates
        """
        if language not in self.VIRAL_HOOKS.get(platform, {}):
            language = 'en'

        return self.VIRAL_HOOKS.get(platform, {}).get(language, [])

    def get_platform_limit(self, platform: str = 'facebook') -> int:
        """Get character limit for platform"""
        return self.PLATFORM_LIMITS.get(platform, 150)
