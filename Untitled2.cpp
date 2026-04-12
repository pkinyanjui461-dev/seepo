#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <cstdlib>
#include <windows.h>

using namespace std;

// Color codes for Windows console
#define COLOR_BLACK 0
#define COLOR_BLUE 1
#define COLOR_GREEN 2
#define COLOR_CYAN 3
#define COLOR_RED 4
#define COLOR_MAGENTA 5
#define COLOR_YELLOW 6
#define COLOR_WHITE 7
#define COLOR_GRAY 8
#define COLOR_LIGHT_BLUE 9
#define COLOR_LIGHT_GREEN 10
#define COLOR_LIGHT_CYAN 11
#define COLOR_LIGHT_RED 12
#define COLOR_LIGHT_MAGENTA 13
#define COLOR_LIGHT_YELLOW 14
#define COLOR_BRIGHT_WHITE 15

HANDLE hConsole = GetStdHandle(STD_OUTPUT_HANDLE);

void setColor(int foreground, int background = 0) {
    SetConsoleTextAttribute(hConsole, (background << 4) | foreground);
}

void clearScreen() {
    system("cls");
}

void pause() {
    cout << "\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  Press any key to continue...";
    setColor(COLOR_WHITE);
    system("pause > nul");
}

// ============================================================================
// CONFIGURATION
// ============================================================================
const string FORK_REPO = "https://github.com/pgwiz/seepo.git";
const string UPSTREAM_REPO = "https://github.com/pkinyanjui461-dev/seepo.git";

void savePATToConfig(const string& configFile, const string& pat) {
    ofstream file(configFile.c_str(), ios::trunc);
    if (file.is_open()) {
        file << "PAT=" << pat << endl;
        file << "# SEEPO Git Sync Configuration\n";
        file << "# Created: " << __DATE__ << " " << __TIME__ << endl;
        file.close();
    }
}

string readConfigPAT(const string& configFile) {
    ifstream file(configFile.c_str());
    if (file.is_open()) {
        string line;
        while (getline(file, line)) {
            if (line.substr(0, 4) == "PAT=") {
                file.close();
                return line.substr(4);
            }
        }
        file.close();
    }
    return "";
}

void printBanner() {
    clearScreen();
    setColor(COLOR_LIGHT_CYAN);
    cout << "\n";
    cout << "  +----------------------------------------------------------------------------+\n";
    cout << "  ¦                                                                            ¦\n";
    setColor(COLOR_LIGHT_YELLOW);
    cout << "  ¦    ¦¦¦¦¦¦¦+¦¦¦¦¦¦¦+¦¦¦¦¦¦¦+¦¦¦¦¦¦+  ¦¦¦¦¦¦+     ¦¦¦¦¦¦¦+¦¦+   ¦¦+¦¦¦+   ¦¦¦+ ¦\n";
    cout << "  ¦    ¦¦+----+¦¦+----+¦¦+----+¦¦+--¦¦+¦¦+---¦¦+    ¦¦+----++¦¦+ ¦¦++¦¦¦¦+ ¦¦¦¦¦ ¦\n";
    cout << "  ¦    ¦¦¦¦¦¦¦+¦¦¦¦¦+  ¦¦¦¦¦+  ¦¦¦¦¦¦++¦¦¦   ¦¦¦    ¦¦¦¦¦¦¦+ +¦¦¦¦++ ¦¦+¦¦¦¦+¦¦¦ ¦\n";
    cout << "  ¦    +----¦¦¦¦¦+--+  ¦¦+--+  ¦¦+---+ ¦¦¦   ¦¦¦    +----¦¦¦  +¦¦++  ¦¦¦+¦¦++¦¦¦ ¦\n";
    cout << "  ¦    ¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦+¦¦¦¦¦¦¦+¦¦¦     +¦¦¦¦¦¦++    ¦¦¦¦¦¦¦¦   ¦¦¦   ¦¦¦ +-+ ¦¦¦ ¦\n";
    cout << "  ¦    +------++------++------++-+      +-----+     +------+   +-+   +-+     +-+ ¦\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  ¦                                                                            ¦\n";
    cout << "  ¦                     ¦¦¦¦¦¦+ ¦¦+¦¦¦¦¦¦¦¦+                                  ¦\n";
    cout << "  ¦                    ¦¦+----+ ¦¦¦+--¦¦+--+                                  ¦\n";
    setColor(COLOR_LIGHT_GREEN);
    cout << "  ¦                    ¦¦¦  ¦¦¦+¦¦¦   ¦¦¦                                     ¦\n";
    cout << "  ¦                    ¦¦¦   ¦¦¦¦¦¦   ¦¦¦                                     ¦\n";
    cout << "  ¦                    +¦¦¦¦¦¦++¦¦¦   ¦¦¦                                     ¦\n";
    cout << "  ¦                     +-----+ +-+   +-+                                     ¦\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  ¦                                                                            ¦\n";
    setColor(COLOR_LIGHT_YELLOW);
    cout << "  ¦                 GitHub Repository Fork & Upstream Sync Tool               ¦\n";
    cout << "  ¦                              Version 1.0                                  ¦\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  ¦                                                                            ¦\n";
    cout << "  +----------------------------------------------------------------------------+\n";
    setColor(COLOR_WHITE);
    cout << "\n";
}

void printMenu() {
    clearScreen();
    setColor(COLOR_LIGHT_CYAN);
    cout << "\n";
    cout << "  +----------------------------------------------------------------------------+\n";
    setColor(COLOR_LIGHT_YELLOW);
    cout << "  ¦                        SELECT BRANCH TO SYNC                              ¦\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  +----------------------------------------------------------------------------+\n";
    cout << "\n";
    setColor(COLOR_WHITE);
    cout << "  \n";
    setColor(COLOR_LIGHT_GREEN);
    cout << "     [1] ? Sync MAIN branch        (Staging)\n";
    setColor(COLOR_LIGHT_MAGENTA);
    cout << "     [2] ? Sync MASTER branch      (Production)\n";
    setColor(COLOR_LIGHT_YELLOW);
    cout << "     [3] ? Sync BOTH branches      (Main ^^ Master)\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "     [4] ? Update PAT Token        (Enter new token)\n";
    setColor(COLOR_RED);
    cout << "     [0] ? EXIT\n";
    setColor(COLOR_WHITE);
    cout << "\n";
    cout << "  ----------------------------------------------------------------------------\n";
    cout << "\n";
}

string getPATInput() {
    string pat;
    printBanner();
    setColor(COLOR_LIGHT_GREEN);
    cout << "  [INFO] Enter your GitHub Personal Access Token (PAT):\n";
    setColor(COLOR_WHITE);
    cout << "  > PAT Token: ";
    getline(cin, pat);

    if (pat.empty()) {
        setColor(COLOR_RED);
        cout << "\n  [ERROR] PAT token cannot be empty!\n";
        setColor(COLOR_WHITE);
        pause();
        return "";
    }

    return pat;
}

void executeSyncCommand(const string& pat, const string& branch) {
    clearScreen();
    setColor(COLOR_LIGHT_CYAN);
    cout << "\n";
    cout << "  +----------------------------------------------------------------------------+\n";
    setColor(COLOR_LIGHT_YELLOW);
    cout << "  ¦                      SYNCING " << (branch == "main" ? "MAIN" : "MASTER") << " BRANCH...                           ¦\n";
    setColor(COLOR_LIGHT_CYAN);
    cout << "  +----------------------------------------------------------------------------+\n";
    setColor(COLOR_WHITE);
    cout << "\n";

    // Construct git URLs with PAT
    string forkURL = "https://" + pat + "@github.com/pgwiz/seepo.git";
    string upstreamURL = "https://github.com/pkinyanjui461-dev/seepo.git";

    // Build git commands for syncing fork with upstream
    stringstream commands;

    // Configure remotes
    commands << "git remote remove origin 2>nul & ";
    commands << "git remote add origin " << forkURL << " & ";
    commands << "git remote remove upstream 2>nul & ";
    commands << "git remote add upstream " << upstreamURL << " & ";

    // Fetch from both remotes
    commands << "git fetch origin --quiet & ";
    commands << "git fetch upstream --quiet & ";

    // Checkout branch or create tracking branch
    commands << "git checkout " << branch << " 2>nul || git checkout --track origin/" << branch << " 2>nul & ";

    // Sync from upstream to origin
    commands << "git pull upstream " << branch << " --quiet & ";
    commands << "git push origin " << branch << " --quiet";

    setColor(COLOR_LIGHT_GREEN);
    cout << "  Repository synced!\n\n";
    cout << "  Current commit info:\n";
    setColor(COLOR_LIGHT_YELLOW);

    system(commands.str().c_str());
    system("git log -1 --pretty=format:\"  Commit: %%h - %%s (%%ar)\"");
    cout << "\n\n";
}

int main() {
    setColor(COLOR_LIGHT_CYAN);

    string configFile = "menu.conf";
    string pat;
    int choice;

    // Try to load PAT from config
    pat = readConfigPAT(configFile);

    if (pat.empty()) {
        pat = getPATInput();
        if (pat.empty()) {
            printBanner();
            setColor(COLOR_RED);
            cout << "  [ERROR] Failed to initialize. Exiting...\n\n";
            setColor(COLOR_WHITE);
            return 1;
        }
        // Save PAT to config
        savePATToConfig(configFile, pat);
        setColor(COLOR_LIGHT_GREEN);
        cout << "\n  [SUCCESS] PAT token saved to menu.conf\n\n";
        setColor(COLOR_WHITE);
        pause();
    } else {
        printBanner();
        setColor(COLOR_LIGHT_GREEN);
        cout << "  [SUCCESS] PAT token loaded from menu.conf\n\n";
        setColor(COLOR_WHITE);
        pause();
    }

    // Main loop
    while (true) {
        printMenu();

        setColor(COLOR_LIGHT_CYAN);
        cout << "  Select option (0-4): ";
        setColor(COLOR_WHITE);

        string input;
        getline(cin, input);

        if (input.empty()) {
            continue;
        }

        choice = atoi(input.c_str());

        switch (choice) {
            case 0:
                clearScreen();
                setColor(COLOR_LIGHT_CYAN);
                cout << "\n";
                cout << "  +----------------------------------------------------------------------------+\n";
                setColor(COLOR_LIGHT_YELLOW);
                cout << "  ¦                                                                            ¦\n";
                cout << "  ¦                 Thank you for using SEEPO Sync (C++)!                     ¦\n";
                cout << "  ¦                                                                            ¦\n";
                setColor(COLOR_LIGHT_CYAN);
                cout << "  +----------------------------------------------------------------------------+\n";
                setColor(COLOR_WHITE);
                cout << "\n";
                return 0;

            case 1:
                executeSyncCommand(pat, "main");
                pause();
                break;

            case 2:
                executeSyncCommand(pat, "master");
                pause();
                break;

            case 3:
                clearScreen();
                setColor(COLOR_LIGHT_CYAN);
                cout << "\n";
                cout << "  +----------------------------------------------------------------------------+\n";
                setColor(COLOR_LIGHT_YELLOW);
                cout << "  ¦                    SYNCING BOTH BRANCHES...                               ¦\n";
                setColor(COLOR_LIGHT_CYAN);
                cout << "  +----------------------------------------------------------------------------+\n";
                setColor(COLOR_WHITE);
                cout << "\n";
                setColor(COLOR_LIGHT_CYAN);
                cout << "  Step 1/2: Syncing MAIN branch...\n";
                setColor(COLOR_LIGHT_GREEN);
                executeSyncCommand(pat, "main");
                setColor(COLOR_LIGHT_GREEN);
                cout << "\n  Step 2/2: Syncing MASTER branch...\n";
                setColor(COLOR_LIGHT_GREEN);
                executeSyncCommand(pat, "master");
                setColor(COLOR_LIGHT_GREEN);
                cout << "  [SUCCESS] Both branches sync complete!\n";
                setColor(COLOR_WHITE);
                pause();
                break;

            case 4:
                pat = getPATInput();
                if (!pat.empty()) {
                    savePATToConfig(configFile, pat);
                    printBanner();
                    setColor(COLOR_LIGHT_GREEN);
                    cout << "  [SUCCESS] PAT token updated and saved to menu.conf\n\n";
                    setColor(COLOR_WHITE);
                    pause();
                }
                break;

            default:
                printBanner();
                setColor(COLOR_RED);
                cout << "  [ERROR] Invalid choice. Please select 0-4.\n\n";
                setColor(COLOR_WHITE);
                pause();
                break;
        }
    }

    return 0;
}

