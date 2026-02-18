"""
Bot LoL Esports - TELEGRAM v2
COM WEB SCRAPING DOS DADOS REAIS!
Extrai direto da mesma fonte que lolesports.com usa
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Dict, List, Optional
import math
import json

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========================================
# CONFIGURAÇÃO
# ========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'SEU_TOKEN_TELEGRAM_AQUI')

# APIs do LoL Esports (mesmas que o site usa!)
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LIVE_STATS_API = "https://feed.lolesports.com/livestats/v1"

# Headers corretos (igual ao site)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Origin': 'https://lolesports.com',
    'Referer': 'https://lolesports.com/',
    'x-api-key': '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'
}

# Ligas principais
MAIN_LEAGUES = ['LCK', 'LPL', 'LEC', 'LCS', 'CBLOL', 'Worlds', 'MSI']

class LoLEsportsAPI:
    """API que replica o comportamento do lolesports.com"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=HEADERS)
        return self.session
    
    async def get_live_games(self) -> List[Dict]:
        """Busca jogos ao vivo (igual ao site)"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getLive?hl=pt-BR"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data.get('data', {}).get('schedule', {}).get('events', [])
                    
                    # Filtrar apenas em andamento e ligas principais
                    live_events = []
                    for event in events:
                        if event.get('state') != 'inProgress':
                            continue
                        
                        league_name = event.get('league', {}).get('name', '')
                        is_main = any(league in league_name for league in MAIN_LEAGUES)
                        
                        if is_main:
                            live_events.append(event)
                    
                    return live_events
        except Exception as e:
            print(f"❌ Erro ao buscar jogos: {e}")
        
        return []
    
    async def get_game_details(self, event_id: str) -> Optional[Dict]:
        """Busca detalhes do evento"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getEventDetails?hl=pt-BR&id={event_id}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('event', {})
        except Exception as e:
            print(f"❌ Erro nos detalhes: {e}")
        
        return None
    
    async def get_live_window(self, game_id: str) -> Optional[Dict]:
        """
        Busca stats AO VIVO - A FORMA CORRETA!
        Usa o endpoint /window/ que o site usa
        """
        session = await self.get_session()
        url = f"{LIVE_STATS_API}/window/{game_id}"
        
        try:
            async with session.get(url, headers=HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # DEBUG: Mostrar o que chegou
                    print(f"✅ Stats recebidas para jogo {game_id}")
                    print(f"   Frames: {len(data.get('frames', []))}")
                    
                    return data
                else:
                    print(f"⚠️ Status {response.status} ao buscar stats")
        except Exception as e:
            print(f"❌ Erro ao buscar window: {e}")
        
        return None
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

class StatsExtractor:
    """Extrai stats dos dados retornados - VERSÃO CORRIGIDA"""
    
    def extract_stats(self, live_data: Dict) -> Optional[Dict]:
        """
        Extrai stats do formato REAL da API
        """
        try:
            frames = live_data.get('frames', [])
            
            if not frames or len(frames) == 0:
                print("⚠️ Sem frames disponíveis")
                return None
            
            # Último frame = estado atual
            latest_frame = frames[-1]
            
            print(f"🔍 Processando frame com {len(latest_frame.keys())} campos")
            
            # Pegar dados dos times
            # A API pode usar 'blueTeam'/'redTeam' OU 'participants' agrupados
            blue_team = latest_frame.get('blueTeam', {})
            red_team = latest_frame.get('redTeam', {})
            
            # Se não tiver blueTeam/redTeam, tentar extrair de participants
            if not blue_team or not red_team:
                participants = latest_frame.get('participants', [])
                if participants:
                    # Agrupar por teamId
                    blue_team = self._aggregate_team(participants, 100)
                    red_team = self._aggregate_team(participants, 200)
            
            # Extrair campos (tentando TODOS os nomes possíveis)
            blue_gold = (
                blue_team.get('totalGold') or 
                blue_team.get('gold') or 
                blue_team.get('goldEarned') or 0
            )
            
            red_gold = (
                red_team.get('totalGold') or 
                red_team.get('gold') or 
                red_team.get('goldEarned') or 0
            )
            
            blue_kills = (
                blue_team.get('totalKills') or 
                blue_team.get('kills') or 
                blue_team.get('championKills') or 0
            )
            
            red_kills = (
                red_team.get('totalKills') or 
                red_team.get('kills') or 
                red_team.get('championKills') or 0
            )
            
            # Torres
            blue_towers = (
                blue_team.get('towersDestroyed') or
                blue_team.get('towers') or
                blue_team.get('towerKills') or 0
            )
            
            red_towers = (
                red_team.get('towersDestroyed') or
                red_team.get('towers') or
                red_team.get('towerKills') or 0
            )
            
            # Dragões
            blue_dragons = (
                blue_team.get('dragonsKilled') or
                blue_team.get('dragons') or
                blue_team.get('dragonKills') or 0
            )
            
            red_dragons = (
                red_team.get('dragonsKilled') or
                red_team.get('dragons') or
                red_team.get('dragonKills') or 0
            )
            
            # Barões
            blue_barons = (
                blue_team.get('baronsKilled') or
                blue_team.get('barons') or
                blue_team.get('baronKills') or 0
            )
            
            red_barons = (
                red_team.get('baronsKilled') or
                red_team.get('barons') or
                red_team.get('baronKills') or 0
            )
            
            # Tempo de jogo
            game_time = latest_frame.get('rfc460Timestamp', 0)
            
            # DEBUG
            print(f"💰 Ouro: Blue={blue_gold} Red={red_gold}")
            print(f"⚔️ Kills: Blue={blue_kills} Red={red_kills}")
            print(f"🏰 Torres: Blue={blue_towers} Red={red_towers}")
            
            # Se TUDO está zerado, retornar None
            total = blue_gold + red_gold + blue_kills + red_kills
            if total == 0:
                print("⚠️ Todos os valores estão zerados - dados ainda não disponíveis")
                return None
            
            # Calcular vantagem
            gold_diff = blue_gold - red_gold
            
            # Probabilidade
            score = (gold_diff / 50000) + ((blue_towers - red_towers) / 11)
            blue_prob = 50 + (50 * math.tanh(score * 2))
            red_prob = 100 - blue_prob
            
            # Resumo
            if abs(gold_diff) < 1000:
                advantage = "⚖️ Equilibrado"
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
                'advantage': advantage,
                'game_time': game_time
            }
            
        except Exception as e:
            print(f"❌ Erro ao extrair stats: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _aggregate_team(self, participants: List[Dict], team_id: int) -> Dict:
        """Agrega stats de participants por time"""
        team_stats = {
            'totalGold': 0,
            'totalKills': 0,
            'towersDestroyed': 0,
            'dragonsKilled': 0,
            'baronsKilled': 0
        }
        
        for p in participants:
            if p.get('teamId') == team_id:
                team_stats['totalGold'] += p.get('totalGold', 0)
                team_stats['totalKills'] += p.get('championKills', 0)
        
        return team_stats

# Instâncias
api = LoLEsportsAPI()
extractor = StatsExtractor()

# ========================================
# COMANDOS TELEGRAM
# ========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🏆 *Bot LoL Esports v2*\n\n"
        "Bot com extração REAL de dados!\n\n"
        "*Comandos:*\n"
        "/live - Ver jogos ao vivo\n"
        "/help - Ajuda\n\n"
        "*Ligas:* LCK • LPL • LEC • LCS • CBLOL",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista jogos ao vivo"""
    msg = await update.message.reply_text("🔍 Buscando jogos...")
    
    try:
        games = await api.get_live_games()
        
        if not games:
            await msg.edit_text(
                "❌ *Nenhum jogo principal ao vivo*\n\n"
                "Ligas: 🇰🇷 LCK • 🇨🇳 LPL • 🇪🇺 LEC • 🇺🇸 LCS • 🇧🇷 CBLOL",
                parse_mode='Markdown'
            )
            return
        
        text = "🔴 *JOGOS AO VIVO*\n\n"
        keyboard = []
        
        for game in games[:10]:
            league = game.get('league', {}).get('name', 'Unknown')
            match = game.get('match', {})
            teams = match.get('teams', [])
            
            if len(teams) >= 2:
                t1 = teams[0].get('code', 'T1')
                t2 = teams[1].get('code', 'T2')
                event_id = game.get('id')
                
                text += f"*{league}*\n{t1} vs {t2}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {t1} vs {t2}",
                        callback_data=f"analyze_{event_id}"
                    )
                ])
        
        await msg.edit_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await msg.edit_text(f"❌ Erro: {str(e)}")

async def analyze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analisa jogo"""
    query = update.callback_query
    await query.answer()
    
    event_id = query.data.replace('analyze_', '')
    
    await query.edit_message_text("📊 Extraindo dados ao vivo...")
    
    try:
        # Buscar detalhes
        event = await api.get_game_details(event_id)
        
        if not event:
            await query.edit_message_text("❌ Evento não encontrado")
            return
        
        match_data = event.get('match', {})
        teams = match_data.get('teams', [])
        games = match_data.get('games', [])
        league = event.get('league', {}).get('name', 'Unknown')
        
        t1_name = teams[0].get('name', 'Blue') if len(teams) > 0 else 'Blue'
        t2_name = teams[1].get('name', 'Red') if len(teams) > 1 else 'Red'
        
        # Jogo em andamento
        current = next((g for g in games if g.get('state') == 'inProgress'), None)
        
        if not current:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\nNenhum jogo rodando agora",
                parse_mode='Markdown'
            )
            return
        
        game_id = current.get('id')
        game_num = current.get('number', 1)
        
        # BUSCAR STATS AO VIVO
        live_data = await api.get_live_window(game_id)
        
        if not live_data:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Jogo {game_num} • Stats indisponíveis\n"
                f"(Pode estar começando)",
                parse_mode='Markdown'
            )
            return
        
        # EXTRAIR STATS
        stats = extractor.extract_stats(live_data)
        
        if not stats:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Dados ainda processando...\n"
                f"Aguarde 2-3 min e clique Atualizar",
                parse_mode='Markdown'
            )
            return
        
        # MONTAR MENSAGEM
        text = f"⚔️ *{t1_name} vs {t2_name}*\n"
        text += f"*{league}* • Jogo {game_num}\n\n"
        
        text += "📊 *PLACAR*\n"
        text += f"{stats['blue_kills']} - {stats['red_kills']}\n\n"
        
        text += f"🔵 *{t1_name}* ({stats['blue_prob']:.0f}%)\n"
        text += f"💰 {stats['blue_gold']:,} | "
        text += f"🏰 {stats['blue_towers']} | "
        text += f"🐉 {stats['blue_dragons']} | "
        text += f"👹 {stats['blue_barons']}\n\n"
        
        text += f"🔴 *{t2_name}* ({stats['red_prob']:.0f}%)\n"
        text += f"💰 {stats['red_gold']:,} | "
        text += f"🏰 {stats['red_towers']} | "
        text += f"🐉 {stats['red_dragons']} | "
        text += f"👹 {stats['red_barons']}\n\n"
        
        text += f"🎯 {stats['advantage']}"
        
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
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajuda"""
    await update.message.reply_text(
        "🏆 *Bot LoL Esports v2*\n\n"
        "*Comandos:*\n"
        "/live - Jogos ao vivo\n"
        "/help - Ajuda\n\n"
        "*Ligas:*\n"
        "🇰🇷 LCK • 🇨🇳 LPL • 🇪🇺 LEC • 🇺🇸 LCS • 🇧🇷 CBLOL",
        parse_mode='Markdown'
    )

def main():
    """Inicia o bot"""
    print("🚀 Bot LoL Esports v2 - COM DADOS REAIS")
    print("="*60)
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("live", live))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(analyze_callback, pattern="^analyze_"))
    
    print("✅ Bot iniciado!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
