import Foundation
import UIKit

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

    func bootstrap() async throws -> BootstrapResponse {
        try await get(path: "/api/mobile/v1/bootstrap/")
    }

    func today(date: Date = Date()) async throws -> TodayResponse {
        let dateString = Self.dayFormatter.string(from: date)
        return try await get(path: "/api/mobile/v1/today/?date=\(dateString)")
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

    private func get<T: Decodable>(path: String) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "GET"
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Decodable>(path: String, body: [String: String]) async throws -> T {
        var request = URLRequest(url: makeURL(path: path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        addAuth(to: &request)
        let (data, response) = try await urlSession.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
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
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
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

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private func makeURL(path: String) -> URL {
        let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        return URL(string: trimmed, relativeTo: baseURL.appendingPathComponent(""))!.absoluteURL
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

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = try? decoder.decode(APIErrorPayload.self, from: data).error
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
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }
}
