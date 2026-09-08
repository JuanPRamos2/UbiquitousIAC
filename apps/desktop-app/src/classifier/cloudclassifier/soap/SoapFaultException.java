package cloudclassifier.soap;

public class SoapFaultException extends Exception {
    private final int httpStatus;
    private final String faultCode;
    private final String userMessage;

    public SoapFaultException(int httpStatus, String faultCode, String userMessage) {
        super(userMessage);
        this.httpStatus = httpStatus;
        this.faultCode = faultCode == null ? "" : faultCode;
        this.userMessage = userMessage;
    }

    public int getHttpStatus() {
        return httpStatus;
    }

    public String getFaultCode() {
        return faultCode;
    }

    public String getUserMessage() {
        return userMessage;
    }

    public boolean isClientFault() {
        return httpStatus >= 400 && httpStatus < 500;
    }

    public boolean isDuplicate() {
        return httpStatus == 409 || userMessage.toLowerCase().contains("ya fue clasificado");
    }
}
