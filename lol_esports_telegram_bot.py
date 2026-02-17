import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Dict, List, Optional
import math

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========================================
# CONFIGURAÇÃO
# ========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'SEU_TOKEN_TELEGRAM_AQUI')
RIOT_API_KEY = os.getenv('RIOT_API_KEY', 'SUA_RIOT_API_KEY_AQUI')

# APIs
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
ESPORTS_FEED = "https://feed.lolesports.com/livestats/v1"

ESPORTS_HEADERS = {
    'x-api-key': '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z',
    'User-Agent': 'Mozilla/5.0'
}

# Ligas principais
MAIN_LEAGUES = {
    'LCK': '98767975604431411',
    'LPL': '98767991302996019', 
    'LEC': '98767991299243165',
    'LCS': '98767991325878492',
    'CBLOL': '98767991332355509'
}

class EsportsAPI:
    """Cliente para LoL Esports API"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=ESPORTS_HEADERS)
        return self.session
    
    async def get_live_matches(self) -> List[Dict]:
        """Busca partidas ao vivo"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getLive?hl=pt-BR"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data.get('data', {}).get('schedule', {}).get('events', [])
                    
                    # Filtrar apenas ligas principais
                    main_events = []
                    for event in events:
                        if event.get('state') != 'inProgress':
                            continue
                        
                        league = event.get('league', {})
                        league_slug = league.get('slug', '')
                        
                        # Verificar se é liga principal
                        is_main = any(
                            main.lower() in league_slug.lower() 
                            for main in MAIN_LEAGUES.keys()
                        )
                        
                        if is_main:
                            main_events.append(event)
                    
                    return main_events
        except Exception as e:
            print(f"Erro ao buscar partidas: {e}")
        
        return []
    
    async def get_event_details(self, event_id: str) -> Optional[Dict]:
        """Busca detalhes do evento"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getEventDetails?hl=pt-BR&id={event_id}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('event', {})
        except Exception as e:
            print(f"Erro ao buscar evento: {e}")
        
        return None
    
    async def get_live_stats(self, game_id: str) -> Optional[Dict]:
        """Busca stats em tempo real"""
        session = await self.get_session()
        url = f"{ESPORTS_FEED}/window/{game_id}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print(f"Stats não disponíveis: {e}")
        
        return None
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class MatchAnalyzer:
    """Analisador de partidas"""
    
    def analyze(self, stats: Dict) -> Optional[Dict]:
        """Analisa stats e retorna resumo"""
        try:
            frames = stats.get('frames', [])
            if not frames:
                return None
            
            latest = frames[-1]
            
            # Teams
            blue = latest.get('blueTeam', {})
            red = latest.get('redTeam', {})
            
            # Dados
            blue_gold = blue.get('totalGold', 0)
            red_gold = red.get('totalGold', 0)
            
            blue_kills = blue.get('totalKills', 0)
            red_kills = red.get('totalKills', 0)
            
            blue_towers = blue.get('towersDestroyed', 0)
            red_towers = red.get('towersDestroyed', 0)
            
            blue_dragons = blue.get('dragonsKilled', 0)
            red_dragons = red.get('dragonsKilled', 0)
            
            blue_barons = blue.get('baronsKilled', 0)
            red_barons = red.get('baronsKilled', 0)
            
            # Tempo
            game_metadata = stats.get('gameMetadata', {})
            
            # Calcular vantagem
            gold_diff = blue_gold - red_gold
            
            # Probabilidade
            score = (gold_diff / 50000) + ((blue_towers - red_towers) / 11) + ((blue_kills - red_kills) / 20)
            blue_prob = 50 + (50 * math.tanh(score * 2))
            red_prob = 100 - blue_prob
            
            # Resumo
            if abs(gold_diff) < 1000:
                advantage = "⚖️ Jogo equilibrado"
            elif gold_diff > 3000:
                advantage = f"🔵 Blue dominando (+{gold_diff:,}g)"
            elif gold_diff < -3000:
                advantage = f"🔴 Red dominando (+{abs(gold_diff):,}g)"
            elif gold_diff > 0:
                advantage = f"🔵 Blue em vantagem (+{gold_diff:,}g)"
            else:
                advantage = f"🔴 Red em vantagem (+{abs(gold_diff):,}g)"
            
            return {
                'blue_gold': blue_gold,
                'red_gold': red_gold,
                'blue_kills': blue_kills,
                'red_kills': red_kills,
                'blue_towers': blue_towers,
                'red_towers': red_towers,
                'blue_dragons': blue_dragons,
                'red_dragons': red_dragons,
                'blue_barons': blue_barons,
                'red_barons': red_barons,
                'gold_diff': gold_diff,
                'blue_prob': blue_prob,
                'red_prob': red_prob,
                'advantage': advantage
            }
            
        except Exception as e:
            print(f"Erro ao analisar: {e}")
            return None

# Instâncias
api = EsportsAPI()
analyzer = MatchAnalyzer()

# ========================================
# COMANDOS TELEGRAM
# ========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🏆 **Bot LoL Esports**\n\n"
        "Acompanhe partidas profissionais em tempo real!\n\n"
        "**Comandos:**\n"
        "/live - Ver jogos ao vivo\n"
        "/help - Ajuda\n\n"
        "**Ligas:** LCK • LPL • LEC • LCS • CBLOL",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /live - Lista jogos ao vivo"""
    msg = await update.message.reply_text("🔍 Buscando partidas ao vivo...")
    
    try:
        matches = await api.get_live_matches()
        
        if not matches:
            await msg.edit_text(
                "❌ **Nenhuma partida ao vivo**\n\n"
                "Ligas monitoradas:\n"
                "🇰🇷 LCK • 🇨🇳 LPL • 🇪🇺 LEC\n"
                "🇺🇸 LCS • 🇧🇷 CBLOL",
                parse_mode='Markdown'
            )
            return
        
        # Criar mensagem
        text = "🔴 **PARTIDAS AO VIVO**\n\n"
        
        keyboard = []
        
        for match in matches[:10]:
            league = match.get('league', {}).get('name', 'Unknown')
            match_obj = match.get('match', {})
            teams = match_obj.get('teams', [])
            
            if len(teams) >= 2:
                team1 = teams[0].get('code', 'T1')
                team2 = teams[1].get('code', 'T2')
                event_id = match.get('id')
                
                text += f"**{league}**\n"
                text += f"{team1} vs {team2}\n\n"
                
                # Botão para analisar
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 Analisar {team1} vs {team2}",
                        callback_data=f"analyze_{event_id}"
                    )
                ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await msg.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await msg.edit_text(f"❌ Erro: {str(e)}")

async def analyze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para análise de partida"""
    query = update.callback_query
    await query.answer()
    
    event_id = query.data.replace('analyze_', '')
    
    await query.edit_message_text("📊 Analisando partida...")
    
    try:
        # Buscar detalhes
        event = await api.get_event_details(event_id)
        
        if not event:
            await query.edit_message_text("❌ Partida não encontrada")
            return
        
        match_data = event.get('match', {})
        teams = match_data.get('teams', [])
        games = match_data.get('games', [])
        league = event.get('league', {}).get('name', 'Unknown')
        
        team1_name = teams[0].get('name', 'Team 1') if len(teams) > 0 else 'Team 1'
        team2_name = teams[1].get('name', 'Team 2') if len(teams) > 1 else 'Team 2'
        
        # Buscar jogo em andamento
        current_game = next((g for g in games if g.get('state') == 'inProgress'), None)
        
        if not current_game:
            await query.edit_message_text(
                f"⚠️ **{team1_name} vs {team2_name}**\n\n"
                f"Nenhum jogo em andamento no momento."
            )
            return
        
        game_id = current_game.get('id')
        game_number = current_game.get('number', 1)
        
        # Buscar stats
        stats = await api.get_live_stats(game_id)
        
        if not stats:
            # Sem stats, mostrar info básica
            await query.edit_message_text(
                f"⚔️ **{team1_name} vs {team2_name}**\n"
                f"**{league}** • Jogo {game_number}\n\n"
                f"⚠️ Stats em tempo real não disponíveis\n"
                f"(Jogo pode estar começando)",
                parse_mode='Markdown'
            )
            return
        
        # Analisar
        analysis = analyzer.analyze(stats)
        
        if not analysis:
            await query.edit_message_text(
                f"⚠️ **{team1_name} vs {team2_name}**\n\n"
                f"Dados ainda processando..."
            )
            return
        
        # Criar mensagem com stats
        text = f"⚔️ **{team1_name} vs {team2_name}**\n"
        text += f"**{league}** • Jogo {game_number}\n\n"
        
        text += "📊 **PLACAR**\n"
        text += f"{analysis['blue_kills']} - {analysis['red_kills']}\n\n"
        
        text += f"🔵 **{team1_name}** ({analysis['blue_prob']:.0f}%)\n"
        text += f"💰 {analysis['blue_gold']:,} | "
        text += f"🏰 {analysis['blue_towers']} | "
        text += f"🐉 {analysis['blue_dragons']} | "
        text += f"👹 {analysis['blue_barons']}\n\n"
        
        text += f"🔴 **{team2_name}** ({analysis['red_prob']:.0f}%)\n"
        text += f"💰 {analysis['red_gold']:,} | "
        text += f"🏰 {analysis['red_towers']} | "
        text += f"🐉 {analysis['red_dragons']} | "
        text += f"👹 {analysis['red_barons']}\n\n"
        
        text += f"🎯 {analysis['advantage']}"
        
        # Botão para atualizar
        keyboard = [[
            InlineKeyboardButton("🔄 Atualizar", callback_data=f"analyze_{event_id}")
        ]]
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Erro: {str(e)}")
        print(f"Erro detalhado: {e}")
        import traceback
        traceback.print_exc()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await update.message.reply_text(
        "🏆 *Bot LoL Esports - Ajuda*\n\n"
        "*Comandos:*\n"
        "/live - Ver partidas ao vivo\n"
        "/help - Esta mensagem\n"
        "/debug - Ver dados brutos da API\n\n"
        "*Ligas Monitoradas:*\n"
        "🇰🇷 LCK • 🇨🇳 LPL • 🇪🇺 LEC • 🇺🇸 LCS • 🇧🇷 CBLOL",
        parse_mode='Markdown'
    )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra dados brutos da API para debug"""
    msg = await update.message.reply_text("🔍 Buscando dados brutos...")
    
    try:
        matches = await api.get_live_matches()
        
        if not matches:
            await msg.edit_text("❌ Nenhuma partida ao vivo agora.")
            return
        
        # Pegar primeiro jogo disponível
        first_match = matches[0]
        match_obj = first_match.get('match', {})
        games = match_obj.get('games', [])
        
        current_game = next((g for g in games if g.get('state') == 'inProgress'), None)
        
        if not current_game:
            await msg.edit_text("❌ Nenhum jogo em andamento.")
            return
        
        game_id = current_game.get('id')
        
        # Buscar stats brutas
        stats = await api.get_live_stats(game_id)
        
        if not stats:
            await msg.edit_text("❌ Stats não disponíveis.")
            return
        
        # Pegar último frame
        frames = stats.get('frames', [])
        if not frames:
            await msg.edit_text("❌ Sem frames disponíveis.")
            return
        
        latest = frames[-1]
        
        # Mostrar TODOS os campos disponíveis
        blue = latest.get('blueTeam', {})
        red = latest.get('redTeam', {})
        
        debug_text = "🔍 *CAMPOS DISPONÍVEIS NA API:*\n\n"
        debug_text += "*🔵 Blue Team campos:*\n"
        for key, value in blue.items():
            if not isinstance(value, (list, dict)):
                debug_text += f"`{key}`: {value}\n"
        
        debug_text += "\n*🔴 Red Team campos:*\n"
        for key, value in red.items():
            if not isinstance(value, (list, dict)):
                debug_text += f"`{key}`: {value}\n"
        
        # Enviar em partes se for muito grande
        if len(debug_text) > 4000:
            debug_text = debug_text[:4000] + "\n...(truncado)"
        
        await msg.edit_text(debug_text, parse_mode='Markdown')
        
    except Exception as e:
        await msg.edit_text(f"❌ Erro: {str(e)}")

# ========================================
# MAIN
# ========================================

def main():
    """Inicia o bot"""
    print("🚀 Iniciando Bot LoL Esports - Telegram")
    print("="*60)
    
    # Criar application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("live", live))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CallbackQueryHandler(analyze_callback, pattern="^analyze_"))
    
    # Rodar
    print("✅ Bot online!")
    application.run_polling()

if __name__ == '__main__':
    main()
