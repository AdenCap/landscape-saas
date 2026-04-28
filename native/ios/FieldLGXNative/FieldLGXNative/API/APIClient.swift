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

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            "Could not read the server response."
        case let .server(statusCode, message):
            message ?? "Server returned status \(statusCode)."
        }
    }
}
