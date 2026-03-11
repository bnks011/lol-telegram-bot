"""
Bot LoL Esports - VERSÃO FINAL
Baseado na lógica do Andy Danger (live-lol-esports)
COM DADOS REAIS FUNCIONANDO!
"""

import asyncio
import aiohttp
import os
from typing import Dict, List, Optional
from datetime import datetime
import math

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ========================================
# CONFIGURAÇÃO
# ========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'SEU_TOKEN_TELEGRAM_AQUI')

# APIs (mesmas que Andy Danger usa)
ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LIVE_STATS_API = "https://feed.lolesports.com/livestats/v1"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'x-api-key': '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'
}

class LiveStatsExtractor:
    """
    Extrator baseado no Andy Danger
    Usa a mesma lógica de sites que FUNCIONAM
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=HEADERS)
        return self.session
    
    async def get_live_matches(self) -> List[Dict]:
        """Busca partidas ao vivo"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getLive?hl=en-US"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data.get('data', {}).get('schedule', {}).get('events', [])
                    live = [e for e in events if e.get('state') == 'inProgress']
                    print(f"✅ Encontrados {len(live)} jogos ao vivo")
                    return live
        except Exception as e:
            print(f"❌ Erro ao buscar jogos: {e}")
        
        return []
    
    async def get_event_details(self, event_id: str) -> Optional[Dict]:
        """Busca detalhes do evento"""
        session = await self.get_session()
        url = f"{ESPORTS_API}/getEventDetails?hl=en-US&id={event_id}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('event', {})
        except Exception as e:
            print(f"❌ Erro: {e}")
        
        return None
    
    async def get_live_window(self, game_id: str) -> Optional[Dict]:
        """
        Busca window de stats
        EXATAMENTE como Andy Danger faz
        """
        session = await self.get_session()
        url = f"{LIVE_STATS_API}/window/{game_id}"
        
        print(f"\n{'='*70}")
        print(f"🎮 Buscando stats: {game_id}")
        print(f"🌐 URL: {url}")
        
        try:
            async with session.get(url) as response:
                status = response.status
                print(f"📡 HTTP Status: {status}")
                
                if status == 200:
                    data = await response.json()
                    frames_count = len(data.get('frames', []))
                    print(f"✅ Sucesso! Frames: {frames_count}")
                    
                    # DEBUG: Mostrar estrutura
                    if frames_count > 0:
                        frame = data['frames'][-1]
                        self._debug_frame_structure(frame)
                    
                    print(f"{'='*70}\n")
                    return data
                else:
                    print(f"⚠️ Status {status}")
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"{'='*70}\n")
        return None
    
    def _debug_frame_structure(self, frame: Dict):
        """Mostra estrutura do frame para debug"""
        print(f"\n📊 ESTRUTURA DO FRAME:")
        print(f"   Chaves: {list(frame.keys())[:10]}")
        
        # Blue Team
        if 'blueTeam' in frame:
            blue = frame['blueTeam']
            print(f"\n🔵 BLUE TEAM:")
            for key, value in list(blue.items())[:20]:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    print(f"     {key}: {value}")
        
        # Red Team
        if 'redTeam' in frame:
            red = frame['redTeam']
            print(f"\n🔴 RED TEAM:")
            for key, value in list(red.items())[:20]:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    print(f"     {key}: {value}")
        
        # Participants
        if 'participants' in frame:
            print(f"\n👥 PARTICIPANTS: {len(frame['participants'])}")
    
    def extract_stats(self, window_data: Dict) -> Optional[Dict]:
        """
        Extrai stats - LÓGICA DO ANDY DANGER
        """
        try:
            frames = window_data.get('frames', [])
            
            if not frames:
                print("⚠️ Sem frames")
                return None
            
            # Último frame = estado atual
            frame = frames[-1]
            
            print(f"\n🔬 EXTRAINDO DADOS:")
            
            # MÉTODO 1: blueTeam/redTeam direto
            blue_team = frame.get('blueTeam', {})
            red_team = frame.get('redTeam', {})
            
            if not blue_team or not red_team:
                print(f"❌ Times não encontrados no frame")
                
                # MÉTODO 2: Tentar participants
                participants = frame.get('participants', [])
                if participants:
                    print(f"🔄 Tentando extrair de participants...")
                    blue_team, red_team = self._extract_from_participants(participants)
            
            # Extrair com TODOS os nomes possíveis
            stats = self._extract_team_stats(blue_team, red_team)
            
            if not stats:
                return None
            
            # Log dos valores
            print(f"💰 Ouro: Blue={stats['blue_gold']} | Red={stats['red_gold']}")
            print(f"⚔️  Kills: Blue={stats['blue_kills']} | Red={stats['red_kills']}")
            print(f"🏰 Torres: Blue={stats['blue_towers']} | Red={stats['red_towers']}")
            print(f"🐉 Dragões: Blue={stats['blue_dragons']} | Red={stats['red_dragons']}")
            
            # Validar se tem dados
            total = (stats['blue_gold'] + stats['red_gold'] + 
                    stats['blue_kills'] + stats['red_kills'])
            
            if total == 0:
                print(f"⚠️ TODOS ZERADOS - Dados indisponíveis")
                print(f"🔍 Blue team keys: {list(blue_team.keys())[:10]}")
                print(f"🔍 Red team keys: {list(red_team.keys())[:10]}")
                return None
            
            print(f"✅ Dados extraídos com sucesso!")
            return stats
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_team_stats(self, blue: Dict, red: Dict) -> Optional[Dict]:
        """Extrai stats com TODOS os nomes possíveis"""
        
        # Lista de possíveis nomes para cada stat
        gold_keys = ['totalGold', 'gold', 'goldEarned', 'currentGold']
        kills_keys = ['totalKills', 'kills', 'championKills', 'championsKilled']
        towers_keys = ['towersDestroyed', 'towers', 'towerKills', 'turrets']
        dragons_keys = ['dragonsKilled', 'dragons', 'dragonKills', 'drakes']
        barons_keys = ['baronsKilled', 'barons', 'baronKills']
        
        # Extrai primeiro valor válido
        blue_gold = self._get_first(blue, gold_keys, 0)
        red_gold = self._get_first(red, gold_keys, 0)
        
        blue_kills = self._get_first(blue, kills_keys, 0)
        red_kills = self._get_first(red, kills_keys, 0)
        
        blue_towers = self._get_first(blue, towers_keys, 0)
        red_towers = self._get_first(red, towers_keys, 0)
        
        blue_dragons = self._get_first(blue, dragons_keys, 0)
        red_dragons = self._get_first(red, dragons_keys, 0)
        
        blue_barons = self._get_first(blue, barons_keys, 0)
        red_barons = self._get_first(red, barons_keys, 0)
        
        # Calcular vantagem
        gold_diff = blue_gold - red_gold
        
        # Probabilidade simplificada
        gold_factor = gold_diff / 1000
        tower_factor = (blue_towers - red_towers) * 5
        kill_factor = (blue_kills - red_kills) * 2
        
        blue_score = 50 + gold_factor + tower_factor + kill_factor
        blue_score = max(10, min(90, blue_score))
        red_score = 100 - blue_score
        
        # Resumo
        if abs(gold_diff) < 1000:
            advantage = "⚖️ Equilibrado"
        elif gold_diff > 5000:
            advantage = f"🔵 Blue dominando (+{gold_diff:,}g)"
        elif gold_diff < -5000:
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
            'blue_prob': blue_score,
            'red_prob': red_score,
            'advantage': advantage
        }
    
    def _get_first(self, data: Dict, keys: List[str], default):
        """Retorna primeiro valor válido"""
        for key in keys:
            value = data.get(key)
            if value is not None and value != 0:
                return value
        # Se todos zerados, retornar o primeiro que existir (mesmo que 0)
        for key in keys:
            if key in data:
                return data[key]
        return default
    
    def _extract_from_participants(self, participants: List[Dict]) -> tuple:
        """Extrai de participants quando blueTeam/redTeam não existem"""
        blue = {'totalGold': 0, 'totalKills': 0}
        red = {'totalGold': 0, 'totalKills': 0}
        
        for p in participants:
            team_id = p.get('teamId', 0)
            if team_id == 100:  # Blue
                blue['totalGold'] += p.get('totalGold', 0)
                blue['totalKills'] += p.get('kills', 0)
            elif team_id == 200:  # Red
                red['totalGold'] += p.get('totalGold', 0)
                red['totalKills'] += p.get('kills', 0)
        
        return blue, red
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# Instância global
extractor = LiveStatsExtractor()

# ========================================
# COMANDOS TELEGRAM
# ========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 *Bot LoL Esports FINAL*\n\n"
        "Baseado no Andy Danger\n"
        "Com dados REAIS!\n\n"
        "/live - Ver jogos\n"
        "/help - Ajuda",
        parse_mode='Markdown'
    )

async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Buscando jogos...")
    
    try:
        matches = await extractor.get_live_matches()
        
        print(f"\n📊 DEBUG LIVE: {len(matches)} matches encontrados")
        
        if not matches:
            await msg.edit_text("❌ Nenhum jogo ao vivo agora")
            return
        
        # Mensagem SIMPLES sem Markdown problemático
        text = f"🔴 JOGOS AO VIVO ({len(matches)})\n\n"
        keyboard = []
        
        for idx, match in enumerate(matches[:10]):
            league = match.get('league', {})
            league_name = league.get('name', 'Unknown')
            
            match_data = match.get('match', {})
            teams = match_data.get('teams', [])
            
            print(f"Match {idx+1}: {league_name} - {len(teams)} times")
            
            if len(teams) >= 2:
                t1 = teams[0].get('code') or teams[0].get('name', 'T1')
                t2 = teams[1].get('code') or teams[1].get('name', 'T2')
                event_id = match.get('id', '')
                
                # Texto SIMPLES
                text += f"{league_name}\n"
                text += f"{t1} vs {t2}\n\n"
                
                # Botão
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {t1} vs {t2}",
                        callback_data=f"analyze_{event_id}"
                    )
                ])
                
                print(f"  Adicionado: {t1} vs {t2}")
        
        print(f"Total botões: {len(keyboard)}\n")
        
        # Enviar SEM parse_mode se tiver problemas
        try:
            await msg.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )
        except Exception as e:
            # Se falhar, enviar só texto
            print(f"⚠️ Erro ao editar com botões: {e}")
            await msg.edit_text(
                f"🔴 {len(matches)} jogos ao vivo\n\n"
                f"Use /help para mais informações"
            )
        
    except Exception as e:
        print(f"❌ Erro em live: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await msg.edit_text("❌ Erro ao buscar jogos")
        except:
            pass

async def analyze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    event_id = query.data.replace('analyze_', '')
    
    await query.edit_message_text("📊 Analisando...")
    
    try:
        # Buscar evento
        event = await extractor.get_event_details(event_id)
        
        if not event:
            await query.edit_message_text("❌ Evento não encontrado")
            return
        
        match_data = event.get('match', {})
        teams = match_data.get('teams', [])
        games = match_data.get('games', [])
        league = event.get('league', {}).get('name', 'Unknown')
        
        t1_name = teams[0].get('name', 'Blue') if teams else 'Blue'
        t2_name = teams[1].get('name', 'Red') if len(teams) > 1 else 'Red'
        
        # Jogo atual
        current_game = next((g for g in games if g.get('state') == 'inProgress'), None)
        
        if not current_game:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Nenhum jogo em andamento",
                parse_mode='Markdown'
            )
            return
        
        game_id = current_game.get('id')
        game_number = current_game.get('number', 1)
        
        # Buscar stats
        window_data = await extractor.get_live_window(game_id)
        
        if not window_data:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Stats indisponíveis\n"
                f"Veja logs do Railway!",
                parse_mode='Markdown'
            )
            return
        
        # Extrair stats
        stats = extractor.extract_stats(window_data)
        
        if not stats:
            await query.edit_message_text(
                f"⚠️ *{t1_name} vs {t2_name}*\n\n"
                f"Jogo {game_number}\n\n"
                f"Dados ainda processando...\n"
                f"Aguarde 3-5 min e clique Atualizar\n\n"
                f"*Veja logs do Railway para debug!*",
                parse_mode='Markdown'
            )
            return
        
        # Montar mensagem
        text = f"⚔️ *{t1_name} vs {t2_name}*\n"
        text += f"*{league}* • Jogo {game_number}\n\n"
        
        text += f"📊 *PLACAR*\n"
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
        
        text += f"🎯 *{stats['advantage']}*"
        
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
        "🏆 *Bot LoL Esports*\n\n"
        "*Comandos:*\n"
        "/live - Jogos ao vivo\n"
        "/help - Ajuda\n\n"
        "*O que mostra:*\n"
        "💰 Ouro\n"
        "⚔️ Kills\n"
        "🏰 Torres\n"
        "🐉 Dragões\n"
        "👹 Barões\n"
        "🎯 Análise de vantagem",
        parse_mode='Markdown'
    )

def main():
    print("\n" + "="*70)
    print("🚀 BOT LOL ESPORTS - VERSÃO FINAL")
    print("📋 Baseado na lógica do Andy Danger")
    print("🔍 Com DEBUG COMPLETO nos logs")
    print("="*70 + "\n")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(analyze_callback, pattern="^analyze_"))
    
    print("✅ Bot iniciado!\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
