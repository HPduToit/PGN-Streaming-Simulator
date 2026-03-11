"""HTTP server that serves PGN files in LiveChess Cloud JSON format.

This server watches the PGN output directory and serves game data
in the same JSON format as LiveChess Cloud, allowing the event_download_manager
to poll it as if it were a real LiveChess Cloud instance.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any as Any, Dict as Dict, List as List, Optional as Optional

import chess
import chess.pgn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class PgnToJsonConverter:
    """Converts PGN files to LiveChess Cloud JSON format."""
    
    @staticmethod
    def parse_pgn_file(pgn_path: Path) -> Optional[chess.pgn.Game]:
        """Parse a PGN file and return the game object."""
        try:
            # Read the entire file content first to ensure we get all moves
            # This is important for files with moves spread across multiple lines
            with open(pgn_path, 'r', encoding='utf-8') as f:
                pgn_content = f.read()
            
            # Parse from string instead of file handle
            from io import StringIO
            pgn_io = StringIO(pgn_content)
            game = chess.pgn.read_game(pgn_io)
            return game
        except Exception as e:
            logger.error(f"Error parsing PGN file {pgn_path}: {e}")
            return None
    
    @staticmethod
    def pgn_to_livechess_json(game: chess.pgn.Game, board: Optional[chess.Board] = None) -> Dict[str, Any]:
        """Convert a PGN game to LiveChess Cloud JSON format.
        
        Args:
            game: The PGN game object
            board: Optional board object (if not provided, will be reconstructed)
        
        Returns:
            Dictionary matching LiveChess Cloud JSON format
        """
        # Extract moves as SAN strings first (before building board)
        # This ensures we get all moves even if the game object has issues
        moves: List[str] = []
        temp_board = game.board()
        mainline_moves_list = list(game.mainline_moves())  # Convert to list to ensure we get all moves
        
        for move in mainline_moves_list:
            moves.append(temp_board.san(move))
            temp_board.push(move)
        
        # Build board state if not provided
        if board is None:
            board = game.board()
            for move in mainline_moves_list:
                board.push(move)
        
        # Determine game result
        result = game.headers.get("Result", "*")
        is_finished = result != "*"
        
        # Build JSON structure matching LiveChess Cloud format
        json_data: Dict[str, Any] = {
            "moves": moves,
            "result": result,
            "finished": is_finished,
        }
        
        # Add clock information if available (default values for simulation)
        # In a real scenario, this would come from the live source
        if not is_finished:
            # Simulate clock times (in centiseconds)
            # You could extend this to read from PGN comments or headers
            json_data["clock"] = {
                "white": 360000,  # 1 hour in centiseconds
                "black": 360000,
            }
        else:
            json_data["clock"] = {
                "white": 0,
                "black": 0,
            }
        
        # Add player information from PGN headers
        if "White" in game.headers:
            json_data["white"] = game.headers["White"]
        if "Black" in game.headers:
            json_data["black"] = game.headers["Black"]
        
        # Add other metadata
        json_data["round"] = game.headers.get("Round", "")
        json_data["event"] = game.headers.get("Event", "")
        
        return json_data


class PgnDirectoryWatcher:
    """Watches a directory for PGN files and maintains an in-memory cache."""
    
    def __init__(self, pgn_directory: Path, active_round: int = 1):
        """Initialize the directory watcher.
        
        Args:
            pgn_directory: Path to the directory containing PGN files
            active_round: Active tournament round to expose via JSON endpoints
        """
        self.pgn_directory = Path(pgn_directory)
        self.pgn_directory.mkdir(parents=True, exist_ok=True)
        self.active_round = active_round
        self.games: Dict[int, chess.pgn.Game] = {}  # board_index -> game
        self.boards: Dict[int, chess.Board] = {}  # board_index -> board
        self.converter = PgnToJsonConverter()
        self._load_all_pgns()

    def _list_board_indices_from_fs(self) -> List[int]:
        """Discover available board PGN files directly from the filesystem.

        Important: PGN writer uses atomic rename which may not trigger watchdog 'modified'
        events reliably (often emits 'moved'). To avoid stale cache issues, endpoints that
        need authoritative state should derive board availability from disk.
        """
        boards: set[int] = set()
        for pgn_file in self.pgn_directory.glob("board_*.pgn"):
            try:
                board_index = int(pgn_file.stem.split("_")[1])
                boards.add(board_index)
            except (ValueError, IndexError):
                continue
        return sorted(boards)
    
    def _load_all_pgns(self) -> None:
        """Load all existing PGN files from the directory."""
        logger.info(f"Loading PGN files from {self.pgn_directory}")
        for pgn_file in self.pgn_directory.glob("board_*.pgn"):
            try:
                board_index = int(pgn_file.stem.split("_")[1])
                game = self.converter.parse_pgn_file(pgn_file)
                if game:
                    self.games[board_index] = game
                    # Reconstruct board state
                    board = game.board()
                    for move in game.mainline_moves():
                        board.push(move)
                    self.boards[board_index] = board
                    logger.debug(f"Loaded PGN for board {board_index}")
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse board index from {pgn_file}: {e}")
            except Exception as e:
                logger.error(f"Error loading {pgn_file}: {e}")
        
        logger.info(f"Loaded {len(self.games)} board PGN files")
    
    def _reload_pgn_file(self, file_path: Path) -> None:
        """Reload a PGN file when it changes."""
        if file_path.suffix == ".pgn" and file_path.name.startswith("board_"):
            # logger.info(f"PGN file changed: {file_path.name}")
            try:
                board_index = int(file_path.stem.split("_")[1])
                game = self.converter.parse_pgn_file(file_path)
                if game:
                    self.games[board_index] = game
                    # Reconstruct board state
                    board = game.board()
                    for move in game.mainline_moves():
                        board.push(move)
                    self.boards[board_index] = board
                    logger.debug(f"Reloaded PGN for board {board_index}")
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse board index from {file_path}: {e}")
            except Exception as e:
                logger.error(f"Error reloading {file_path}: {e}")
    
    def start_watching(self) -> Observer:
        """Start watching the directory for changes using watchdog.
        
        Returns:
            Observer instance that can be stopped later
        """
        class PgnFileHandler(FileSystemEventHandler):
            def __init__(self, watcher: PgnDirectoryWatcher):
                self.watcher = watcher
            
            def on_modified(self, event):
                if not event.is_directory:
                    self.watcher._reload_pgn_file(Path(event.src_path))
            
            def on_created(self, event):
                if not event.is_directory:
                    self.watcher._reload_pgn_file(Path(event.src_path))

            def on_moved(self, event):
                # Atomic writes often emit moved events (temp file -> final filename).
                if not getattr(event, "is_directory", False):
                    try:
                        dest = getattr(event, "dest_path", None)
                        if dest:
                            self.watcher._reload_pgn_file(Path(dest))
                    except Exception:
                        pass

            def on_deleted(self, event):
                if not event.is_directory:
                    try:
                        p = Path(event.src_path)
                        if p.suffix == ".pgn" and p.name.startswith("board_"):
                            board_index = int(p.stem.split("_")[1])
                            self.watcher.games.pop(board_index, None)
                            self.watcher.boards.pop(board_index, None)
                    except Exception:
                        pass
        
        observer = Observer()
        handler = PgnFileHandler(self)
        observer.schedule(handler, str(self.pgn_directory), recursive=False)
        observer.start()
        logger.info(f"Started watching {self.pgn_directory} for changes")
        return observer
    
    def get_game_json(self, board_index: int) -> Optional[Dict[str, Any]]:
        """Get the JSON representation of a game for a specific board.
        
        Args:
            board_index: The board number (1-based)
        
        Returns:
            JSON dictionary or None if board not found
        """
        # Always reload from file to ensure we have the latest moves
        # This is important because the file might be updated while we're serving requests
        pgn_file = self.pgn_directory / f"board_{board_index}.pgn"
        if not pgn_file.exists():
            return None
        
        game = self.converter.parse_pgn_file(pgn_file)
        if game is None:
            return None
        
        # Reconstruct board state
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
        
        return self.converter.pgn_to_livechess_json(game, board)
    
    def get_available_boards(self) -> List[int]:
        """Get list of available board indices."""
        # Prefer filesystem discovery to avoid stale in-memory state.
        boards = self._list_board_indices_from_fs()
        return boards or sorted(self.games.keys())
    
    def get_tournament_info(self) -> Dict[str, Any]:
        """Get tournament-level information."""
        boards = self.get_available_boards()
        rounds: list[dict[str, Any]] = []
        if boards:
            live_count = 0
            for b in boards:
                game_json = self.get_game_json(b)
                if game_json and not bool(game_json.get("finished", False)):
                    live_count += 1
            rounds = [{"count": len(boards), "live": 0} for _ in range(self.active_round)]
            rounds[self.active_round - 1] = {"count": len(boards), "live": live_count}
        return {"rounds": rounds}
    
    def get_round_index(self, round_no: int) -> Dict[str, Any]:
        """Get round index information (pairings).
        
        Args:
            round_no: Round number
        
        Returns:
            Dictionary with pairings information
        """
        boards = self.get_available_boards()
        pairings: list[dict[str, Any]] = []

        # Authoritative: derive pairings from the same file-read path as game-{board}.json.
        for board_index in boards:
            game_json = self.get_game_json(board_index)
            if not game_json:
                continue
            white_player_number = (board_index * 2) - 1
            black_player_number = board_index * 2
            white = game_json.get("white") or f"Player {white_player_number}"
            black = game_json.get("black") or f"Player {black_player_number}"
            result = game_json.get("result", "*")
            finished = bool(game_json.get("finished", False))
            pairings.append(
                {
                    "white": {"name": white},
                    "black": {"name": black},
                    "result": result,
                    "live": not finished,
                }
            )

        return {"pairings": pairings}
    
    def _is_finished(self, board_index: int) -> bool:
        """Check if a game is finished."""
        game_json = self.get_game_json(board_index)
        if game_json is None:
            return False
        return bool(game_json.get("finished", False))


# Global watcher instance
_watcher: Optional[PgnDirectoryWatcher] = None
_observer: Optional[Observer] = None


def _parse_positive_int(value: str, env_name: str) -> Optional[int]:
    """Parse and validate a positive integer value."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s value '%s'; expected integer >= 1",
            env_name,
            value,
        )
        return None
    if parsed < 1:
        logger.warning(
            "Invalid %s value '%s'; expected integer >= 1",
            env_name,
            value,
        )
        return None
    return parsed


def _load_round_from_config(config_path: str) -> Optional[int]:
    """Load configured round from a YAML config file if available."""
    path = Path(config_path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning("Unexpected YAML structure in %s; expected mapping", path)
            return None
        round_number = data.get("round_number", data.get("round_index", data.get("round")))
        if round_number is None:
            return None
        parsed = _parse_positive_int(str(round_number), "round_number")
        if parsed is None:
            logger.warning("Ignoring invalid round_number in %s", path)
        return parsed
    except Exception as e:
        logger.warning("Failed reading PGN config at %s: %s", path, e)
        return None


def _default_config_candidates() -> list[Path]:
    """Build default config search paths when PGN_CONFIG_PATH is not provided."""
    candidates: list[Path] = []
    cwd_config = Path.cwd() / "config.yaml"
    candidates.append(cwd_config)
    repo_config = Path(__file__).resolve().parents[2] / "config.yaml"
    if repo_config not in candidates:
        candidates.append(repo_config)
    return candidates


def _resolve_active_round() -> int:
    """Resolve active round from env/config with sensible defaults."""
    env_round = os.getenv("PGN_ACTIVE_ROUND")
    if env_round:
        parsed = _parse_positive_int(env_round, "PGN_ACTIVE_ROUND")
        if parsed is not None:
            logger.info("Using active round from PGN_ACTIVE_ROUND=%s", parsed)
            return parsed

    env_config_path = os.getenv("PGN_CONFIG_PATH")
    if env_config_path:
        config_round = _load_round_from_config(env_config_path)
        if config_round is not None:
            logger.info(
                "Using active round %s from config file %s",
                config_round,
                env_config_path,
            )
            return config_round
        logger.warning(
            "No valid round found in PGN_CONFIG_PATH=%s; falling back to defaults",
            env_config_path,
        )
    else:
        for candidate in _default_config_candidates():
            config_round = _load_round_from_config(str(candidate))
            if config_round is not None:
                logger.info(
                    "Using active round %s from config file %s",
                    config_round,
                    candidate,
                )
                return config_round

    logger.info("Using default active round 1")
    return 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI startup and shutdown."""
    global _watcher, _observer
    
    # Startup
    pgn_dir = os.getenv("PGN_OUTPUT_DIRECTORY", "./pgn_output")
    active_round = _resolve_active_round()
    _watcher = PgnDirectoryWatcher(pgn_dir, active_round=active_round)
    _observer = _watcher.start_watching()
    logger.info("PGN server started (active round %s)", active_round)
    
    yield
    
    # Shutdown
    if _observer:
        _observer.stop()
        _observer.join()
    logger.info("PGN server stopped")


app = FastAPI(
    title="PGN Simulator Server",
    description="Serves PGN files as LiveChess Cloud JSON",
    lifespan=lifespan
)


@app.get("/get/{code}/tournament.json")
async def get_tournament(code: str):
    """Get tournament information.
    
    The code parameter is ignored but kept for compatibility with LiveChess Cloud API.
    """
    if _watcher is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    tournament_info = _watcher.get_tournament_info()
    
    # Add ETag support for caching
    response = JSONResponse(content=tournament_info)
    response.headers["ETag"] = f'"{hash(str(tournament_info))}"'
    return response


@app.get("/get/{code}/round-{round_no}/index.json")
async def get_round_index(code: str, round_no: int):
    """Get round index (pairings) information.
    
    Args:
        code: Tournament code (ignored)
        round_no: Round number
    """
    if _watcher is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    if round_no != _watcher.active_round:
        raise HTTPException(
            status_code=404,
            detail=f"Round {round_no} not found (active round is {_watcher.active_round})",
        )
    
    round_info = _watcher.get_round_index(round_no)
    
    # Add ETag support for caching
    response = JSONResponse(content=round_info)
    response.headers["ETag"] = f'"{hash(str(round_info))}"'
    return response


@app.get("/get/{code}/round-{round_no}/game-{board_no}.json")
async def get_game_json(code: str, round_no: int, board_no: int, poll: Optional[str] = None):
    """Get game JSON for a specific board.
    
    Args:
        code: Tournament code (ignored)
        round_no: Round number
        board_no: Board number (1-based)
        poll: Optional poll parameter (for compatibility with LiveChess Cloud)
    """
    if _watcher is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    if round_no != _watcher.active_round:
        raise HTTPException(
            status_code=404,
            detail=f"Round {round_no} not found (active round is {_watcher.active_round})",
        )
    
    game_json = _watcher.get_game_json(board_no)
    if game_json is None:
        raise HTTPException(status_code=404, detail=f"Board {board_no} not found")
    
    # Add ETag support for caching
    response = JSONResponse(content=game_json)
    # Use move count as version for ETag
    move_count = len(game_json.get("moves", []))
    response.headers["ETag"] = f'"{move_count}"'
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "watcher_initialized": _watcher is not None,
        "active_round": _watcher.active_round if _watcher else None,
    }


def main():
    """Main entry point for the PGN server CLI."""
    import uvicorn
    import os
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    host = os.getenv("PGN_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("PGN_SERVER_PORT", "8006"))
    pgn_dir = os.getenv("PGN_OUTPUT_DIRECTORY", "./pgn_output")
    
    logger.info(f"Starting PGN server on {host}:{port}")
    logger.info(f"Watching PGN directory: {pgn_dir}")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
