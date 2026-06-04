import Foundation
import UIKit

enum FieldLGXConfig {
    static var apiBaseURL: URL {
        if let value = Bundle.main.object(forInfoDictionaryKey: "FIELDLGX_API_BASE_URL") as? String,
           let url = URL(string: value),
           !value.isEmpty,
           value.hasPrefix("http"),
           !value.contains("$(") {
            return url
        }
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("--fieldlgx-local-api") {
            return URL(string: "http://127.0.0.1:8004")!
        }
        #endif
        return URL(string: "https://app.fieldlgx.com")!
    }
}

struct APIClient {
    var baseURL: URL
    var accessToken: String?
    var urlSession: URLSession = .shared

    func login(email: String, password: String) async throws -> LoginResponse {
        try await post(path: "/api/mobile/v1/auth/login/", body: [
            "email": email,
            "password": password,
            "platform": "ios",
            "device_name": UIDevice.current.name
        ])
    }

    func refresh(refreshToken: String) async throws -> LoginResponse {
        try await post(path: "/api/mobile/v1/auth/refresh/", body: [
            "refresh_token": refreshToken
        ])
    }

    func appleLogin(identityToken: String) async throws -> LoginResponse {
        try await post(path: "/api/mobile/v1/auth/apple/", body: [
            "identity_token": identityToken,
            "platform": "ios",
            "device_name": UIDevice.current.name
        ])
    }

    func bootstrap() async throws -> BootstrapResponse {
        try await get(path: "/api/mobile/v1/bootstrap/")
    }

    func command(date: Date? = nil) async throws -> CommandResponse {
        if let date {
            let dateString = Self.dayFormatter.string(from: date)
            return try await get(path: "/api/mobile/v1/command/?date=\(dateString)")
        }
        return try await get(path: "/api/mobile/v1/command/")
    }

    func search(query: String) async throws -> SearchResponse {
        let value = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await get(path: "/api/mobile/v1/search/?q=\(value)")
    }

    func work(date: Date = Date(), service: String = "all") async throws -> WorkResponse {
        let dateString = Self.dayFormatter.string(from: date)
        let serviceValue = service.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? service
        return try await get(path: "/api/mobile/v1/work/?date=\(dateString)&service=\(serviceValue)")
    }

    func calendar(date: Date? = nil, view: String = "week") async throws -> CalendarResponse {
        if let date {
            let dateString = Self.dayFormatter.string(from: date)
            return try await get(path: "/api/mobile/v1/calendar/?date=\(dateString)&view=\(view)")
        }
        return try await get(path: "/api/mobile/v1/calendar/?view=\(view)")
    }

    func money() async throws -> MoneyResponse {
        try await get(path: "/api/mobile/v1/money/")
    }

    func financials() async throws -> FinancialsResponse {
        try await get(path: "/api/mobile/v1/financials/")
    }

    func team() async throws -> TeamResponse {
        try await get(path: "/api/mobile/v1/team/")
    }

    func agreements() async throws -> AgreementsResponse {
        try await get(path: "/api/mobile/v1/agreements/")
    }

    func ownerSettings() async throws -> OwnerSettingsResponse {
        try await get(path: "/api/mobile/v1/settings/")
    }

    func monthlyInvoices() async throws -> MonthlyInvoiceQueueResponse {
        try await get(path: "/api/mobile/v1/monthly-invoices/")
    }

    func sendMonthlyInvoices(invoiceIDs: [Int], sendAllReady: Bool = false) async throws -> MonthlyInvoiceQueueResponse {
        try await postJSONObject(path: "/api/mobile/v1/monthly-invoices/", body: [
            "action": sendAllReady ? "send_all_ready" : "send_selected",
            "invoice_ids": invoiceIDs
        ])
    }

    func invoiceDetail(id: Int) async throws -> InvoiceDetailResponse {
        try await get(path: "/api/mobile/v1/invoices/\(id)/")
    }

    func estimateDetail(id: Int) async throws -> EstimateDetailResponse {
        try await get(path: "/api/mobile/v1/estimates/\(id)/")
    }

    func createInvoice(customerID: Int, dueDate: String, enableCardPayment: Bool, description: String, detailDescription: String, quantity: String, unitPrice: String) async throws -> InvoiceDetailResponse {
        try await createInvoice(payload: [
            "customer_id": customerID,
            "due_date": dueDate,
            "enable_card_payment": enableCardPayment,
            "line_items": [[
                "description": description,
                "detail_description": detailDescription,
                "quantity": quantity,
                "unit_price": unitPrice
            ]]
        ])
    }

    func createInvoice(payload: [String: Any]) async throws -> InvoiceDetailResponse {
        try await postJSONObject(path: "/api/mobile/v1/invoices/", body: payload)
    }

    func createEstimate(customerID: Int, title: String, notes: String, validUntil: String, depositRequired: Bool, depositType: String, depositAmount: String, description: String, detailDescription: String, quantity: String, unit: String, unitPrice: String) async throws -> EstimateDetailResponse {
        try await createEstimate(payload: [
            "customer_id": customerID,
            "title": title,
            "notes": notes,
            "valid_until": validUntil,
            "deposit_required": depositRequired,
            "deposit_type": depositType,
            "deposit_amount": depositAmount,
            "line_items": [[
                "description": description,
                "detail_description": detailDescription,
                "quantity": quantity,
                "unit": unit,
                "unit_price": unitPrice
            ]]
        ])
    }

    func createEstimate(payload: [String: Any]) async throws -> EstimateDetailResponse {
        try await postJSONObject(path: "/api/mobile/v1/estimates/", body: payload)
    }

    func invoiceAction(id: Int, action: String) async throws -> InvoiceActionResponse {
        try await post(path: "/api/mobile/v1/invoices/\(id)/action/", body: ["action": action])
    }

    func setInvoiceLineItemPaid(invoiceID: Int, itemID: Int, paid: Bool, paymentMethod: String = "") async throws -> InvoiceDetailResponse {
        try await post(path: "/api/mobile/v1/invoices/\(invoiceID)/line-items/\(itemID)/action/", body: [
            "action": paid ? "paid" : "unpaid",
            "payment_method": paymentMethod
        ])
    }

    func estimateAction(id: Int, action: String, selectedOptionalIDs: [Int] = []) async throws -> EstimateActionResponse {
        var body: [String: Any] = ["action": action]
        if !selectedOptionalIDs.isEmpty {
            body["selected_optional_ids"] = selectedOptionalIDs
        }
        return try await postJSONObject(path: "/api/mobile/v1/estimates/\(id)/action/", body: body)
    }

    func uploadEstimatePhoto(id: Int, imageData: Data, caption: String = "", fileName: String = "estimate-photo.jpg") async throws -> EstimatePhotoUploadResponse {
        try await postMultipart(
            path: "/api/mobile/v1/estimates/\(id)/photos/",
            fieldName: "image",
            fileName: fileName,
            mimeType: "image/jpeg",
            fileData: imageData,
            formFields: ["caption": caption]
        )
    }

    func uploadReceipt(imageData: Data, jobID: Int? = nil, receiptDate: String, amount: String, vendor: String, description: String, category: String = "materials", fileName: String = "receipt.jpg") async throws -> ReceiptUploadResponse {
        var fields = [
            "receipt_date": receiptDate,
            "amount": amount,
            "vendor": vendor,
            "description": description,
            "category": category
        ]
        if let jobID {
            fields["job_id"] = "\(jobID)"
        }
        return try await postMultipart(
            path: "/api/mobile/v1/receipts/",
            fieldName: "file",
            fileName: fileName,
            mimeType: "image/jpeg",
            fileData: imageData,
            formFields: fields
        )
    }

    func jobOptions() async throws -> JobOptionsResponse {
        try await get(path: "/api/mobile/v1/jobs/options/")
    }

    func createJob(propertyID: Int, scheduledDate: String, scheduledTime: String, notes: String, serviceItem: JobCreateServiceItem?, crewID: Int? = nil) async throws -> JobDetailResponse {
        var body: [String: Any] = [
            "property_id": propertyID,
            "scheduled_date": scheduledDate,
            "scheduled_time": scheduledTime,
            "notes": notes
        ]
        if let crewID {
            body["assigned_crew_id"] = crewID
        }
        if let serviceItem {
            body["service_items"] = [serviceItem.dictionary]
        }
        return try await postJSONObject(path: "/api/mobile/v1/jobs/", body: body)
    }

    func updateJob(
        id: Int,
        scheduledDate: String,
        scheduledTime: String,
        scheduledEndDate: String? = nil,
        scheduledEndTime: String? = nil,
        notes: String,
        status: String? = nil,
        crewID: Int? = nil,
        clearCrew: Bool = false,
        color: String? = nil,
        routeOrder: Int? = nil,
        serviceItems: [JobCreateServiceItem]? = nil
    ) async throws -> JobDetailResponse {
        var body: [String: Any] = [
            "scheduled_date": scheduledDate,
            "scheduled_time": scheduledTime,
            "notes": notes
        ]
        if let scheduledEndDate {
            body["scheduled_end_date"] = scheduledEndDate
        }
        if let scheduledEndTime {
            body["scheduled_end_time"] = scheduledEndTime
        }
        if let status {
            body["status"] = status
        }
        if clearCrew {
            body["assigned_crew_id"] = NSNull()
        } else if let crewID {
            body["assigned_crew_id"] = crewID
        }
        if let color {
            body["color"] = color
        }
        if let routeOrder {
            body["route_order"] = routeOrder
        }
        if let serviceItems {
            body["service_items"] = serviceItems.map(\.dictionary)
        }
        return try await patch(path: "/api/mobile/v1/jobs/\(id)/", body: body)
    }

    func today(date: Date = Date()) async throws -> TodayResponse {
        let dateString = Self.dayFormatter.string(from: date)
        return try await get(path: "/api/mobile/v1/today/?date=\(dateString)")
    }

    func clients(query: String = "") async throws -> ClientsResponse {
        let value = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await get(path: "/api/mobile/v1/clients/?q=\(value)")
    }

    func client(id: Int) async throws -> ClientDetailResponse {
        try await get(path: "/api/mobile/v1/clients/\(id)/")
    }

    func createClient(name: String, email: String, phone: String, address: String, notes: String) async throws -> ClientDetailResponse {
        try await post(path: "/api/mobile/v1/clients/", body: [
            "name": name,
            "email": email,
            "phone": phone,
            "address": address,
            "notes": notes
        ])
    }

    func timeClockStatus() async throws -> TimeClockResponse {
        try await get(path: "/api/mobile/v1/time-clock/")
    }

    func clockIn(latitude: Double? = nil, longitude: Double? = nil) async throws -> TimeClockResponse {
        try await post(path: "/api/mobile/v1/time-clock/clock-in/", body: coordinateBody(latitude: latitude, longitude: longitude))
    }

    func clockOut(latitude: Double? = nil, longitude: Double? = nil) async throws -> TimeClockResponse {
        try await post(path: "/api/mobile/v1/time-clock/clock-out/", body: coordinateBody(latitude: latitude, longitude: longitude))
    }

    func sendTimeClockLocation(latitude: Double, longitude: Double, accuracy: Double? = nil) async throws -> TimeClockLocationResponse {
        var body = coordinateBody(latitude: latitude, longitude: longitude)
        if let accuracy {
            body["accuracy"] = String(format: "%.2f", accuracy)
        }
        return try await post(path: "/api/mobile/v1/time-clock/location/", body: body)
    }

    func jobDetail(id: Int) async throws -> JobDetailResponse {
        try await get(path: "/api/mobile/v1/jobs/\(id)/")
    }

    func startJob(id: Int) async throws -> JobDetailResponse {
        try await post(path: "/api/mobile/v1/jobs/\(id)/start/", body: [:])
    }

    func completeJob(id: Int) async throws -> JobDetailResponse {
        try await post(path: "/api/mobile/v1/jobs/\(id)/complete/", body: [:])
    }

    func skipJob(id: Int, reason: String) async throws -> JobDetailResponse {
        try await post(path: "/api/mobile/v1/jobs/\(id)/skip/", body: ["reason": reason])
    }

    func uploadCompletionPhoto(id: Int, imageData: Data, fileName: String = "completion.jpg") async throws -> JobDetailResponse {
        try await postMultipart(
            path: "/api/mobile/v1/jobs/\(id)/completion-photo/",
            fieldName: "image",
            fileName: fileName,
            mimeType: "image/jpeg",
            fileData: imageData
        )
    }

    func uploadJobPhoto(id: Int, imageData: Data, category: String, fileName: String = "job-photo.jpg") async throws -> JobDetailResponse {
        try await postMultipart(
            path: "/api/mobile/v1/jobs/\(id)/photos/",
            fieldName: "image",
            fileName: fileName,
            mimeType: "image/jpeg",
            fileData: imageData,
            formFields: ["category": category]
        )
    }

    func addJobNote(id: Int, text: String) async throws -> JobDetailResponse {
        try await post(path: "/api/mobile/v1/jobs/\(id)/notes/", body: ["text": text, "visibility": "crew"])
    }

    func reportJobIssue(id: Int, issueType: String, description: String) async throws -> JobDetailResponse {
        try await post(path: "/api/mobile/v1/jobs/\(id)/issues/", body: [
            "issue_type": issueType,
            "description": description
        ])
    }

    func performQueuedJobMutation(jobID: Int, payload: [String: String]) async throws -> JobDetailResponse {
        switch payload["action"] {
        case "start":
            try await startJob(id: jobID)
        case "complete":
            try await completeJob(id: jobID)
        case "skip":
            try await skipJob(id: jobID, reason: payload["reason"] ?? "Skipped from offline queue.")
        case "add_note":
            try await addJobNote(id: jobID, text: payload["text"] ?? "")
        case "report_issue":
            try await reportJobIssue(
                id: jobID,
                issueType: payload["issue_type"] ?? "other",
                description: payload["description"] ?? ""
            )
        default:
            throw APIError.unsupportedQueuedMutation
        }
    }

    func syncPush(localID: String, entityType: String, operation: String, payload: [String: Any]) async throws -> SyncPushResponse {
        try await postJSONObject(path: "/api/mobile/v1/sync/push/", body: [
            "mutations": [
                [
                    "local_id": localID,
                    "entity_type": entityType,
                    "operation": operation,
                    "payload": payload
                ]
            ]
        ])
    }

    private func get<T: Decodable>(path: String) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "GET"
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data, path: path)
        return try decode(T.self, from: data, path: path)
    }

    private func post<T: Decodable>(path: String, body: [String: String]) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data, path: path)
        return try decode(T.self, from: data, path: path)
    }

    private func patch<T: Decodable>(path: String, body: [String: Any]) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data, path: path)
        return try decode(T.self, from: data, path: path)
    }

    private func postJSONObject<T: Decodable>(path: String, body: [String: Any]) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data, path: path)
        return try decode(T.self, from: data, path: path)
    }

    private func postMultipart<T: Decodable>(
        path: String,
        fieldName: String,
        fileName: String,
        mimeType: String,
        fileData: Data,
        formFields: [String: String] = [:]
    ) async throws -> T {
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = multipartBody(
            boundary: boundary,
            fieldName: fieldName,
            fileName: fileName,
            mimeType: mimeType,
            fileData: fileData,
            formFields: formFields
        )
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data, path: path)
        return try decode(T.self, from: data, path: path)
    }

    private func multipartBody(
        boundary: String,
        fieldName: String,
        fileName: String,
        mimeType: String,
        fileData: Data,
        formFields: [String: String]
    ) -> Data {
        var body = Data()
        for (name, value) in formFields {
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            body.append(value)
            body.append("\r\n")
        }
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"\(fieldName)\"; filename=\"\(fileName)\"\r\n")
        body.append("Content-Type: \(mimeType)\r\n\r\n")
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n")
        return body
    }

    private var decoder: JSONDecoder {
        JSONDecoder()
    }

    private func decode<T: Decodable>(_ type: T.Type, from data: Data, path: String) throws -> T {
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            #if DEBUG
            let body = String(data: data, encoding: .utf8) ?? "<non-utf8 response>"
            print("FIELDLGX API decode failed for \(path): \(error)")
            print("FIELDLGX API response body for \(path): \(body.prefix(4000))")
            #endif
            throw error
        }
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private func makeURL(path: String) -> URL {
        let baseString = baseURL.absoluteString.hasSuffix("/") ? baseURL.absoluteString : "\(baseURL.absoluteString)/"
        let relativePath = path.hasPrefix("/") ? String(path.dropFirst()) : path
        return URL(string: relativePath, relativeTo: URL(string: baseString)!)!.absoluteURL
    }

    private func addAuth(to request: inout URLRequest) {
        if let accessToken {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }
    }

    private func coordinateBody(latitude: Double?, longitude: Double?) -> [String: String] {
        guard let latitude, let longitude else { return [:] }
        return [
            "latitude": String(format: "%.7f", latitude),
            "longitude": String(format: "%.7f", longitude)
        ]
    }

    private func validate(response: URLResponse, data: Data, path: String) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = try? decoder.decode(APIErrorPayload.self, from: data).error
            #if DEBUG
            let body = String(data: data, encoding: .utf8) ?? "<non-utf8 response>"
            print("FIELDLGX API server error for \(path): status \(http.statusCode), message \(message ?? "none")")
            print("FIELDLGX API error body for \(path): \(body.prefix(4000))")
            #endif
            throw APIError.server(statusCode: http.statusCode, message: message)
        }
    }
}

private struct APIErrorPayload: Decodable {
    let error: String?
}

enum APIError: LocalizedError {
    case invalidResponse
    case server(statusCode: Int, message: String?)
    case unsupportedQueuedMutation

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "Could not read the server response."
        case let .server(statusCode, message):
            message ?? "Server returned status \(statusCode)."
        case .unsupportedQueuedMutation:
            "This offline action is not supported yet."
        }
    }

    var statusCode: Int? {
        if case let .server(statusCode, _) = self {
            return statusCode
        }
        return nil
    }
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }
}
