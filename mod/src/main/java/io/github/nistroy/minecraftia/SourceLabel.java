package io.github.nistroy.minecraftia;

/** Libellé lisible d'une source renvoyée par le cerveau ; url seulement pour les liens https cliquables. */
public record SourceLabel(String label, String url) {
    private static final String FICHE = "kb:mods/";
    private static final String NOTE = "note:notes/";
    private static final String RECIPE = "data:recipe:";
    private static final String ITEM = "data:item:";
    private static final String HTTPS = "https://";

    public static SourceLabel of(String source) {
        if (source.startsWith(FICHE) && source.endsWith(".md")) {
            return new SourceLabel("fiche " + source.substring(FICHE.length(), source.length() - 3), null);
        }
        if (source.startsWith(NOTE)) {
            String rest = source.substring(NOTE.length());
            int slash = rest.indexOf('/');
            return new SourceLabel("note " + (slash > 0 ? rest.substring(0, slash) : rest), null);
        }
        if (source.startsWith(RECIPE)) {
            return new SourceLabel("recette " + source.substring(RECIPE.length()), null);
        }
        if (source.startsWith(ITEM)) {
            return new SourceLabel("données " + source.substring(ITEM.length()), null);
        }
        if (source.startsWith(HTTPS)) {
            return new SourceLabel(source.substring(HTTPS.length()), source);
        }
        return new SourceLabel(source, null);
    }
}
