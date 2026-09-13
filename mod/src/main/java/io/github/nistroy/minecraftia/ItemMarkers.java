package io.github.nistroy.minecraftia;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Marqueurs d'icônes écrits par le cerveau dans une réponse : [[ns:id]] (item) ou [[#ns:tag]] (groupe d'items). */
public final class ItemMarkers {
    private static final String ID = "[a-z0-9_.-]+:[a-z0-9_./-]+";
    private static final Pattern MARKER = Pattern.compile("\\[\\[(#?)(" + ID + ")\\]\\]");
    private static final Pattern WITH_SPACE = Pattern.compile("\\s?\\[\\[#?" + ID + "\\]\\]");

    public sealed interface Segment permits Text, Icon {
    }

    public record Text(String text) implements Segment {
    }

    /** id sans le « # » ; tag = groupe d'items (ex. toutes les planches). */
    public record Icon(String id, boolean tag) implements Segment {
    }

    private ItemMarkers() {
    }

    public static List<Segment> parse(String text) {
        List<Segment> segments = new ArrayList<>();
        Matcher marker = MARKER.matcher(text);
        int last = 0;
        while (marker.find()) {
            if (marker.start() > last) {
                segments.add(new Text(text.substring(last, marker.start())));
            }
            segments.add(new Icon(marker.group(2), !marker.group(1).isEmpty()));
            last = marker.end();
        }
        if (last < text.length()) {
            segments.add(new Text(text.substring(last)));
        }
        return segments;
    }

    /** Texte sans marqueurs, pour le chat : le cerveau écrit toujours le nom de l'item avant son marqueur. */
    public static String strip(String text) {
        return WITH_SPACE.matcher(text).replaceAll("");
    }
}
