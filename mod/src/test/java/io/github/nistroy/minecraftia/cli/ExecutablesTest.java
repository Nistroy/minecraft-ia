package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ExecutablesTest {
    private static final Path HOME = Path.of("C:/Users/Jean Dupont");

    private static Executables.Env windows(String path, Set<Path> files) {
        return new Executables.Env(true, Map.of("PATH", path, "PATHEXT", ".COM;.EXE;.BAT;.CMD",
                "APPDATA", "C:/Users/Jean Dupont/AppData/Roaming"), HOME, files::contains);
    }

    @Test
    void windowsPrefersPathOrderThenPathext() {
        Path cmd = Path.of("C:/tools/claude.cmd");
        Path exe = Path.of("C:/bin/claude.exe");
        Executables.Env env = windows("C:/tools;C:/bin", Set.of(cmd, exe));
        assertEquals(Optional.of(cmd), Executables.find("claude", "", env));
    }

    @Test
    void windowsFallsBackToNpmAndLocalBin() {
        Path npm = Path.of("C:/Users/Jean Dupont/AppData/Roaming/npm/codex.cmd");
        Path local = HOME.resolve(".local/bin/claude.exe");
        Executables.Env env = windows("C:/Windows", Set.of(npm, local));
        assertEquals(Optional.of(npm), Executables.find("codex", "", env));
        assertEquals(Optional.of(local), Executables.find("claude", "", env));
        assertEquals(Optional.empty(), Executables.find("agy", "", env));
    }

    @Test
    void posixUsesPathWithoutExtension() {
        Path claude = Path.of("/usr/local/bin/claude");
        Executables.Env env = new Executables.Env(false, Map.of("PATH", "/usr/bin:/usr/local/bin"), Path.of("/home/j"),
                Set.of(claude)::contains);
        assertEquals(Optional.of(claude), Executables.find("claude", "", env));
    }

    @Test
    void configuredPathWinsButMustExist() {
        Path custom = Path.of("D:/ia/claude.exe");
        assertEquals(Optional.of(custom), Executables.find("claude", "D:/ia/claude.exe", windows("", Set.of(custom))));
        assertEquals(Optional.empty(), Executables.find("claude", "D:/absent.exe", windows("", Set.of())));
    }

    @Test
    void batchFilesRejectCmdMetacharacters() {
        Path cmd = Path.of("C:/npm/claude.cmd");
        assertTrue(Executables.safeArgs(cmd, List.of("-p", "--tools", "", "--mcp-config", "C:/Users/Jean Dupont/x.json")));
        for (String bad : List.of("a&b", "a|b", "a\"b", "100%", "a^b", "a<b", "a>b", "a!b", "a\nb")) {
            assertFalse(Executables.safeArgs(cmd, List.of(bad)), bad);
        }
        assertTrue(Executables.safeArgs(Path.of("C:/bin/agy.exe"), List.of("a&b \"c\"")));
    }
}
