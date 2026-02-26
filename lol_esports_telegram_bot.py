import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
from typing import Dict, List, Optional
import json
import re

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========================================
# CONFIGURAÇÃO
# ========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'SEU_TOKEN_TELEGRAM_AQUI')

# LoL Esports URLs
LOLESPORTS_BASE = "https://lolesports.com"
LOLESPORTS_LIVE = f"{LOLESPORTS_BASE}/live"

# APIs de fallback
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LIVE_STATS_API = "https://feed.lolesports.com/livestats/v1"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://lolesports.com/'
}

API_HEADERS = {
    'x-api-key': '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z',
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json'
}

class LoLScraper:
    """Scraper que extrai dados do lolesports.com E usa API como fallback"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_live_games(self) -> List[Dict]:
        """
        Busca jogos ao vivo da API
        (HTML do lolesports é React - precisa JS para renderizar)
        """
        session = await self.get_session()
        url = f"{ESPORTS_API}/getLive?hl=pt-BR"
        
        try:
            async with session.get(url, headers=API_HEADERS) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data.get('data', {}).get('schedule', {}).get('events', [])
                    
                    # Filtrar ao vivo
                    live = [e for e in events if e.get('state') == 'inProgress']
                    return live
        except Exception as e:
            print(f"❌ Erro ao buscar jogos: {e}")
        
        return []
    
    async def get_game_stats_from_feed(self, game_id: str) -> Optional[Dict]:
        """
        Busca stats direto do FEED que o site usa
        Este é o endpoint REAL que alimenta o lolesports.com
        """
        session = await self.get_session()
        
        # Endpoint que o site REALMENTE usa
        url = f"https://feed.lolesports.com/livestats/v1/window/{game_id}"
        
        print(f"🔍 Buscando stats do jogo: {game_id}")
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extrair informações REAIS
                    frames = data.get('frames', [])
                    
                    if not frames:
                        print("⚠️ Sem frames disponíveis")
                        return None
                    
                    latest = frames[-1]
                    game_metadata = data.get('gameMetadata', {})
                    
                    print(f"✅ Dados recebidos! Frames: {len(frames)}")
                    
                    # EXTRAIR DADOS - Testando TODOS os formatos possíveis
                    result = self._extract_all_possible_fields(latest, game_metadata)
                    
                    if result:
                        print(f"💰 Ouro extraído: Blue={result.get('blue_gold')} Red={result.get('red_gold')}")
                        print(f"⚔️ Kills extraídos: Blue={result.get('blue_kills')} Red={result.get('red_kills')}")
                    
                    return result
                else:
                    print(f"⚠️ Status {response.status}")
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        return None
    
    def _extract_all_possible_fields(self, frame: Dict, metadata: Dict) -> Optional[Dict]:
        """
        Tenta TODOS os formatos possíveis de extração
        """
        try:
            # Formato 1: blueTeam/redTeam direto
            blue_team = frame.get('blueTeam', {})
            red_team = frame.get('redTeam', {})
            
            # Formato 2: participants agrupados
            if not blue_team or not red_team:
                participants = frame.get('participants', [])
                if participants:
                    blue_team, red_team = self._group_by_team(participants)
            
            # Formato 3: Dados no nível do frame
            if not blue_team:
                # Alguns feeds colocam dados direto no frame
                if 'totalGold' in frame or 'gold' in frame:
                    blue_team = {k: v for k, v in frame.items() if not k.startswith('red')}
                    red_team = {k: v for k, v in frame.items() if k.startswith('red')}
            
            # EXTRAIR com TODOS os nomes possíveis
            blue_gold = self._get_first_valid(blue_team, 
                ['totalGold', 'gold', 'goldEarned', 'currentGold', 'teamGold'], 0)
            
            red_gold = self._get_first_valid(red_team,
                ['totalGold', 'gold', 'goldEarned', 'currentGold', 'teamGold'], 0)
            
            blue_kills = self._get_first_valid(blue_team,
                ['totalKills', 'kills', 'championKills', 'teamKills'], 0)
            
            red_kills = self._get_first_valid(red_team,
                ['totalKills', 'kills', 'championKills', 'teamKills'], 0)
            
            blue_towers = self._get_first_valid(blue_team,
                ['towersDestroyed', 'towers', 'towerKills', 'inhibitors'], 0)
            
            red_towers = self._get_first_valid(red_team,
                ['towersDestroyed', 'towers', 'towerKills', 'inhibitors'], 0)
            
            blue_dragons = self._get_first_valid(blue_team,
                ['dragonsKilled', 'dragons', 'dragonKills'], 0)
            
            red_dragons = self._get_first_valid(red_team,
                ['dragonsKilled', 'dragons', 'dragonKills'], 0)
            
            blue_barons = self._get_first_valid(blue_team,
                ['baronsKilled', 'barons', 'baronKills'], 0)
            
            red_barons = self._get_first_valid(red_team,
                ['baronsKilled', 'barons', 'baronKills'], 0)
            
            # Se TUDO zerado, dados não disponíveis
            total = blue_gold + red_gold + blue_kills + red_kills
            if total == 0:
                print("⚠️ Todos valores zerados - dados indisponíveis")
                
                # DEBUG: Mostrar TODOS os campos disponíveis
                print(f"🔍 Campos em blueTeam: {list(blue_team.keys())}")
                print(f"🔍 Campos em redTeam: {list(red_team.keys())}")
                print(f"🔍 Campos no frame: {list(frame.keys())}")
                
                return None
            
            # Calcular vantagem
            gold_diff = blue_gold - red_gold
            
            # Probabilidade simplificada
            blue_prob = 50 + (gold_diff / 1000)
            blue_prob = max(10, min(90, blue_prob))
            red_prob = 100 - blue_prob
            
            # Resumo
            if abs(gold_diff) < 1000:
                advantage = "⚖️ Equilibrado"
            elif gold_diff > 3000:
                advantage = f"🔵 Blue +{gold_diff:,}g"
            elif gold_diff < -3000:
                advantage = f"🔴 Red +{abs(gold_diff):,}g"
            elif gold_diff > 0:
                advantage = f"🔵 Blue +{gold_diff:,}g"
            else:
                advantage = f"🔴 Red +{abs(gold_diff):,}g"
            
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
            print(f"❌ Erro na extração: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_first_valid(self, data: Dict, keys: List[str], default=0):
        """Retorna o primeiro valor válido encontrado"""
        for key in keys:
            value = data.get(key)
            if value is not None and value != 0:
                return value
        return default
    
    def _group_by_team(self, participants: List[Dict]) -> tuple:
        """Agrupa participants por time"""
        blue = {'totalGold': 0, 'totalKills': 0}
        red = {'totalGold': 0, 'totalKills': 0}
        
        for p in participants:
            team_id = p.get('teamId', 0)
            if team_id == 100:
                blue['totalGold'] += p.get('totalGold', 0)
                blue['totalKills'] += p.get('championKills', 0)
            elif team_id == 200:
                red['totalGold'] += p.get('totalGold', 0)
                red['totalKills'] += p.get('championKills', 0)
        
        return blue, red
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# Instância
scraper = LoLScraper()

# ========================================
# COMANDOS TELEGRAM
# ========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 *Bot LoL Esports v3*\n\n"
        "Extração DIRETA dos dados!\n\n"
        "/live - Ver jogos\n"
        "/help - Ajuda",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Buscando...")
    
    try:
        games = await scraper.get_live_games()
        
        if not games:
            await msg.edit_text("❌ Nenhum jogo ao vivo agora")
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
    query = update.callback_query
    await query.answer()
    
    event_id = query.data.replace('analyze_', '')
    
    await query.edit_message_text("📊 Extraindo dados...")
    
    try:
        # Buscar detalhes
        session = await scraper.get_session()
        url = f"{ESPORTS_API}/getEventDetails?hl=pt-BR&id={event_id}"
        
        async with session.get(url, headers=API_HEADERS) as response:
            if response.status != 200:
                await query.edit_message_text("❌ Evento não encontrado")
                return
            
            data = await response.json()
            event = data.get('data', {}).get('event', {})
        
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
                f"⚠️ *{t1_name} vs {t2_name}*\n\nNenhum jogo rodando",
                parse_mode='Markdown'
            )
            return
        
        game_id = current.get('id')
        game_num = current.get('number', 1)
        
        # BUSCAR STATS COM SCRAPING
        stats = await scraper.get_game_stats_from_feed(game_id)
        
        if not stats:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Jogo {game_num}\n\n"
                f"Dados ainda não disponíveis\n"
                f"(Aguarde 3-5 min e clique Atualizar)",
                parse_mode='Markdown'
            )
            return
        
        # MONTAR MENSAGEM
        text = f"⚔️ *{t1_name} vs {t2_name}*\n"
        text += f"*{league}* • Jogo {game_num}\n\n"
        
        text += f"📊 *PLACAR*\n{stats['blue_kills']} - {stats['red_kills']}\n\n"
        
        text += f"🔵 *{t1_name}* ({stats['blue_prob']:.0f}%)\n"
        text += f"💰 {stats['blue_gold']:,} | 🏰 {stats['blue_towers']} | "
        text += f"🐉 {stats['blue_dragons']} | 👹 {stats['blue_barons']}\n\n"
        
        text += f"🔴 *{t2_name}* ({stats['red_prob']:.0f}%)\n"
        text += f"💰 {stats['red_gold']:,} | 🏰 {stats['red_towers']} | "
        text += f"🐉 {stats['red_dragons']} | 👹 {stats['red_barons']}\n\n"
        
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
    await update.message.reply_text(
        "🏆 *Bot LoL Esports v3*\n\n"
        "/live - Jogos ao vivo\n"
        "/help - Ajuda",
        parse_mode='Markdown'
    )

def main():
    print("🚀 Bot LoL Esports v3 - Scraping Direto!")
    print("="*60)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(analyze_callback, pattern="^analyze_"))
    
    print("✅ Bot online!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
