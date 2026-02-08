#include "recomp_ui.h"
#include "zelda_config.h"
#include "zelda_support.h"
#include "librecomp/game.hpp"
#include "recomp_input.h"
#include "ultramodern/ultramodern.hpp"
#include "RmlUi/Core.h"
#include "nfd.h"
#include "SDL.h"
#include <filesystem>

static std::string version_string;

Rml::DataModelHandle model_handle;
bool mm_rom_valid = false;

extern std::vector<recomp::GameEntry> supported_games;

// Auto-start: mirror BanjoRecomp's behavior (SDL timer -> SDL_USEREVENT -> start_game on main thread).
static bool hm64_autostart_scheduled = false;
static std::u8string hm64_autostart_game_id;

static Uint32 hm64_autostart_timer_callback(Uint32 interval, void* param) {
    (void)interval;
    (void)param;
    fprintf(stderr, "[hm64] autostart timer fired\n");
    fflush(stderr);

    SDL_Event event;
    SDL_zero(event);
    event.type = SDL_USEREVENT;
    event.user.code = recomp::RECOMP_AUTOSTART_EVENT_CODE;
    event.user.data1 = (void*)hm64_autostart_game_id.c_str();
    event.user.data2 = nullptr;
    SDL_PushEvent(&event);
    return 0;
}

void select_rom() {
    nfdnchar_t* native_path = nullptr;
    zelda64::open_file_dialog([](bool success, const std::filesystem::path& path) {
        if (success) {
            recomp::RomValidationError rom_error = recomp::select_rom(path, supported_games[0].game_id);
            switch (rom_error) {
                case recomp::RomValidationError::Good:
                    mm_rom_valid = true;
                    model_handle.DirtyVariable("mm_rom_valid");
                    break;
                case recomp::RomValidationError::FailedToOpen:
                    recompui::message_box("Failed to open ROM file.");
                    break;
                case recomp::RomValidationError::NotARom:
                    recompui::message_box("This is not a valid ROM file.");
                    break;
                case recomp::RomValidationError::IncorrectRom:
                    recompui::message_box("This ROM is not the correct game.");
                    break;
                case recomp::RomValidationError::NotYet:
                    recompui::message_box("This game isn't supported yet.");
                    break;
                case recomp::RomValidationError::IncorrectVersion:
                    recompui::message_box(
                            "This ROM is the correct game, but the wrong version.\nThis project requires the NTSC-U N64 version of the game.");
                    break;
                case recomp::RomValidationError::OtherError:
                    recompui::message_box("An unknown error has occurred.");
                    break;
            }
        }
    });
}

recompui::ContextId launcher_context;

recompui::ContextId recompui::get_launcher_context_id() {
	return launcher_context;
}

class LauncherMenu : public recompui::MenuController {
public:
    LauncherMenu() {
        mm_rom_valid = recomp::is_rom_valid(supported_games[0].game_id);
    }
    ~LauncherMenu() override {

    }
    void load_document() override {
		launcher_context = recompui::create_context(zelda64::get_asset_path("launcher.rml"));
    }
    void register_events(recompui::UiEventListenerInstancer& listener) override {
        recompui::register_event(listener, "select_rom",
            [](const std::string& param, Rml::Event& event) {
                select_rom();
            }
        );
        recompui::register_event(listener, "rom_selected",
            [](const std::string& param, Rml::Event& event) {
                mm_rom_valid = true;
                model_handle.DirtyVariable("mm_rom_valid");
            }
        );
        recompui::register_event(listener, "start_game",
            [](const std::string& param, Rml::Event& event) {
                // Make "Start game" robust even if the ROM was just selected in this session:
                // load the stored ROM into memory first, and fail gracefully if it's missing.
                std::u8string game_id = supported_games[0].game_id;
                if (!recomp::load_stored_rom(game_id)) {
                    recompui::message_box("No valid stored ROM found. Please select a ROM first.");
                    return;
                }
                recomp::start_game(game_id);
                recompui::hide_all_contexts();
            }
        );
        recompui::register_event(listener, "open_controls",
            [](const std::string& param, Rml::Event& event) {
                recompui::set_config_tab(recompui::ConfigTab::Controls);
                recompui::hide_all_contexts();
                recompui::show_context(recompui::get_config_context_id(), "");
            }
        );
        recompui::register_event(listener, "open_settings",
            [](const std::string& param, Rml::Event& event) {
                recompui::set_config_tab(recompui::ConfigTab::General);
                recompui::hide_all_contexts();
                recompui::show_context(recompui::get_config_context_id(), "");
            }
        );
        recompui::register_event(listener, "open_mods",
            [](const std::string &param, Rml::Event &event) {
                recompui::set_config_tab(recompui::ConfigTab::Mods);
                recompui::hide_all_contexts();
                recompui::show_context(recompui::get_config_context_id(), "");
            }
        );
        recompui::register_event(listener, "exit_game",
            [](const std::string& param, Rml::Event& event) {
                ultramodern::quit();
            }
        );
    }
    void make_bindings(Rml::Context* context) override {
        Rml::DataModelConstructor constructor = context->CreateDataModel("launcher_model");

        constructor.Bind("mm_rom_valid", &mm_rom_valid);

        version_string = recomp::get_project_version().to_string();
        constructor.Bind("version_number", &version_string);

        model_handle = constructor.GetModelHandle();

        // Schedule autostart after the launcher UI is initialized.
        // Default: enabled, 4 seconds delay. Disable with RECOMP_AUTOSTART=0.
        if (!hm64_autostart_scheduled && !supported_games.empty()) {
            const char* autostart_env = std::getenv("RECOMP_AUTOSTART");
            bool autostart_enabled = true;
            if (autostart_env != nullptr && autostart_env[0] != '\0') {
                autostart_enabled = (autostart_env[0] != '0');
            }

            int delay_ms = 4000;
            const char* delay_env = std::getenv("RECOMP_AUTOSTART_DELAY_MS");
            if (delay_env != nullptr && delay_env[0] != '\0') {
                int parsed = std::atoi(delay_env);
                if (parsed >= 0) {
                    delay_ms = parsed;
                }
            }

            if (autostart_enabled) {
                hm64_autostart_scheduled = true;
                hm64_autostart_game_id = supported_games[0].game_id;
                SDL_AddTimer((Uint32)delay_ms, hm64_autostart_timer_callback, nullptr);
                fprintf(stderr, "[hm64] autostart scheduled in %dms\n", delay_ms);
                fflush(stderr);
            }
        }
    }
};

std::unique_ptr<recompui::MenuController> recompui::create_launcher_menu() {
    return std::make_unique<LauncherMenu>();
}
