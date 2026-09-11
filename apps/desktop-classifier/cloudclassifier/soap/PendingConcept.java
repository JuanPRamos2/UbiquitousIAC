package cloudclassifier.soap;

public final class PendingConcept {
    public final int conceptId;
    public final String conceptName;
    public final String definition;
    public final String isbn;
    public final String bookTitle;
    public final String categoryName;

    public PendingConcept(int conceptId, String conceptName, String definition,
                          String isbn, String bookTitle, String categoryName) {
        this.conceptId = conceptId;
        this.conceptName = conceptName;
        this.definition = definition;
        this.isbn = isbn;
        this.bookTitle = bookTitle;
        this.categoryName = categoryName;
    }

    @Override
    public String toString() {
        return conceptName + " — " + bookTitle + " (" + categoryName + ")";
    }
}
